"""A6: local Hugging Face model for plain-English line-item explanations.

transformers downloads the weights into the Hugging Face cache the first time a
pipeline is built, so a fresh clone needs no manual download step.
"""
import hashlib
import logging
import threading

from django.conf import settings
from django.core.cache import cache

from . import guardrails, prompts

log = logging.getLogger(__name__)

_pipeline = None
_lock = threading.Lock()


class LocalModelUnavailable(RuntimeError):
    pass


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
            # float32 is fastest on CPUs without bf16 support; bfloat16 halves RAM for bigger models.
            _pipeline = pipeline("text-generation", model=settings.LOCAL_LLM_MODEL,
                                 dtype=getattr(torch, settings.LOCAL_LLM_DTYPE), device_map="cpu")
    return _pipeline


def _generate(messages):
    pipe = get_pipeline()
    # Same decoding as the notebook benchmark: greedy, and stop at the first "}" (end of the JSON object).
    out = pipe(messages, max_new_tokens=settings.LOCAL_LLM_MAX_TOKENS, do_sample=False,
               return_full_text=False, stop_strings=["}"], tokenizer=pipe.tokenizer)
    return out[0]["generated_text"]


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
    return {**result, "flag": "review" if issues else result["flag"], "issues": issues}
