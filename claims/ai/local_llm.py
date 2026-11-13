"""A6: local Hugging Face model for plain-English line-item explanations.

transformers downloads the weights into the Hugging Face cache the first time a
pipeline is built, so a fresh clone needs no manual download step.
"""
import hashlib
import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache

from . import guardrails, prompts, usage

log = logging.getLogger(__name__)

_pipeline = None
_lock = threading.Lock()


class LocalModelUnavailable(RuntimeError):
    pass


def resolve_device(torch):
    """LOCAL_LLM_DEVICE: cpu (default), mps (Apple-silicon GPU), cuda, or auto."""
    wanted = settings.LOCAL_LLM_DEVICE
    if wanted == "auto":
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        return "mps" if mps is not None and mps.is_available() else "cpu"
    return wanted


def get_pipeline():
    """Load the model once per process; later calls reuse it."""
    global _pipeline
    if not settings.LOCAL_LLM_ENABLED:
        raise LocalModelUnavailable("The local model is turned off on this server (LOCAL_LLM_ENABLED=0).")
    with _lock:
        if _pipeline is None:
            try:
                import torch
                from transformers import pipeline
            except ImportError as exc:
                raise LocalModelUnavailable("torch and transformers are not installed on this server.") from exc
            torch.set_num_threads(settings.LOCAL_LLM_THREADS)
            device = resolve_device(torch)
            # float32 is safest on a plain CPU; on an Apple-silicon GPU (mps) or CUDA, float16 halves
            # RAM and is several times faster (A9 latency fix, see README_AI.md 3.4).
            dtype = settings.LOCAL_LLM_DTYPE or ("float32" if device == "cpu" else "float16")
            log.info("Loading %s on %s (%s)", settings.LOCAL_LLM_MODEL, device, dtype)
            _pipeline = pipeline("text-generation", model=settings.LOCAL_LLM_MODEL,
                                 dtype=getattr(torch, dtype), device=device)
    return _pipeline


def generate(messages, max_new_tokens, stop_strings=None, max_seconds=None):
    """Greedy decoding with a hard time limit (A9 guardrail): transformers stops generating after
    max_seconds, so a slow CPU returns a short answer instead of hanging the request."""
    pipe = get_pipeline()
    kwargs = {"max_new_tokens": max_new_tokens, "do_sample": False, "return_full_text": False,
              "max_time": max_seconds or settings.LOCAL_LLM_MAX_SECONDS}
    if stop_strings:
        kwargs.update(stop_strings=stop_strings, tokenizer=pipe.tokenizer)
    start = time.perf_counter()
    out = pipe(messages, **kwargs)
    text = out[0]["generated_text"]
    usage.add(*count_tokens(pipe.tokenizer, messages, text), time.perf_counter() - start)
    return text


def count_tokens(tokenizer, messages, text):
    """(prompt tokens incl. chat template, completion tokens) with the model's own tokenizer.
    Analytics only: returns (0, 0) instead of raising if the tokenizer API differs."""
    try:
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        if hasattr(ids, "keys"):  # some versions return a BatchEncoding
            ids = ids["input_ids"]
        prompt = len(ids[0]) if ids and isinstance(ids[0], list) else len(ids)
        completion = len(tokenizer(text or "", add_special_tokens=False)["input_ids"])
        return prompt, completion
    except Exception:
        log.debug("Token count failed", exc_info=True)
        return 0, 0


def _generate(messages):
    # Same decoding as the notebook benchmark: greedy, and stop at the first "}" (end of the JSON object).
    # A reply cut off by the time limit is incomplete JSON, so parse_explanation turns it into the fallback.
    return generate(messages, settings.LOCAL_LLM_MAX_TOKENS, stop_strings=["}"])


def rules_only(item):
    """Fallback when no local model can run (e.g. PythonAnywhere without torch): the
    deterministic checks still flag the item, and appeal letters still work."""
    issues = guardrails.rule_checks(item)
    return {"category": "Not classified", "explanation": "", "flag": "review" if issues else "ok",
            "source": "rules", "issues": issues}


def explain_line_item(item):
    """Return {"category", "explanation", "flag", "source", "issues"} for one BillLineItem.

    Results are cached per line item and model, so reopening a bill is instant.
    """
    fact_sheet = guardrails.describe_line_item(item)
    key = f"a6-explain:{settings.LOCAL_LLM_MODEL}:{item.pk}:{hashlib.sha256(fact_sheet.encode()).hexdigest()[:16]}"
    issues = guardrails.rule_checks(item)
    result = cache.get(key)
    if result is None:
        raw = _generate(prompts.zero_shot_messages(fact_sheet))
        result = guardrails.parse_explanation(raw)
        if result is None:
            log.warning("Unusable model output for line item %s: %r", item.pk, raw[:200])
            result = {"category": "Other", "flag": "review", "source": "fallback",
                      "explanation": "The AI could not produce a reliable explanation for this charge."}
        else:
            result["source"] = "model"
        cache.set(key, result, 60 * 60 * 24)
    # The rule checks always win: a model saying "ok" never hides a real problem.
    # model_flag keeps the model's own answer so the A9 evaluation can tell the two apart.
    return {**result, "model_flag": result["flag"], "flag": "review" if issues else result["flag"], "issues": issues}
