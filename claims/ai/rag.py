"""A9: "Ask about my plan" -- retrieval-augmented answers from the local model.

    question ──► check_question ──► retrieval.search (plan-filtered, thresholded)
                                         │ no chunk above the threshold → "no_results", the LLM is NOT called
                                         ▼
                              prompts.rag_messages (numbered excerpts)
                                         ▼
                      local Qwen2.5-1.5B-Instruct (greedy, max_new_tokens, max_time)
                                         ▼
                 guardrails.check_answer (citations, unsupported numbers) ──► page

Everything runs on the Django server with public models; no paid API is involved.
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

from . import guardrails, local_llm, prompts, retrieval

log = logging.getLogger(__name__)


@dataclass
class Answer:
    question: str
    status: str             # answered | not_found | no_results | model_off | fallback | retrieval_only
    text: str = ""
    hits: list = field(default_factory=list)
    citations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    backend: str = ""
    best_score: float = 0.0
    retrieval_ms: float = 0.0
    generation_s: float = 0.0
    total_s: float = 0.0
    cached: bool = False
    llm_called: bool = False

    @property
    def grounded(self):
        return self.status in {"answered", "not_found"} and (self.status == "not_found" or bool(self.citations))


def answer_question(question, plan=None, *, k=None, min_score=None, filter_by_plan=None,
                    use_llm=True, use_cache=True):
    """Raises guardrails.UnsafeInput for empty/too-long/injection questions; never raises for a
    missing or failing model (the status says what happened instead)."""
    start = time.perf_counter()
    question = guardrails.check_question(question)
    found = retrieval.search(question, plan, k=k, min_score=min_score, filter_by_plan=filter_by_plan)
    answer = Answer(question=question, status="no_results", hits=found.hits, notes=list(found.notes),
                    backend=found.backend, best_score=found.best_score, retrieval_ms=found.milliseconds)

    if not found.hits:  # nothing relevant: say so instead of letting the model guess
        answer.total_s = round(time.perf_counter() - start, 2)
        return answer
    if not use_llm:
        answer.status = "retrieval_only"
        answer.total_s = round(time.perf_counter() - start, 2)
        return answer

    sources = [hit.chunk.text for hit in found.hits]
    key = "a9-rag:" + hashlib.sha256("|".join(
        [settings.LOCAL_LLM_MODEL, question.lower(), *[h.chunk.id for h in found.hits], *sources]).encode()).hexdigest()
    checked = cache.get(key) if use_cache else None
    if checked is not None:
        answer.cached = True
    else:
        gen_start = time.perf_counter()
        try:
            answer.llm_called = True
            raw = local_llm.generate(prompts.rag_messages(question, found.hits), settings.RAG_MAX_TOKENS,
                                     max_seconds=settings.RAG_MAX_SECONDS)
        except local_llm.LocalModelUnavailable as exc:
            answer.status = "model_off"
            answer.notes.append(str(exc))
            answer.total_s = round(time.perf_counter() - start, 2)
            return answer
        answer.generation_s = round(time.perf_counter() - gen_start, 2)
        checked = guardrails.check_answer(raw, sources)
        if checked is None:
            log.warning("Unusable RAG output for %r: %r", question, (raw or "")[:200])
        if checked is not None and answer.generation_s >= settings.RAG_MAX_SECONDS * 0.95:
            checked["warnings"].append("The answer hit the time limit and may be cut off.")
        if checked is not None:
            cache.set(key, checked, 60 * 60 * 24)

    if checked is None:
        answer.status = "fallback"
        answer.text = "The AI could not produce a reliable answer. The plan sections below are the closest matches."
    else:
        answer.status = "not_found" if checked["not_found"] else "answered"
        answer.text, answer.citations, answer.warnings = checked["text"], checked["citations"], checked["warnings"]
    answer.total_s = round(time.perf_counter() - start, 2)
    return answer


def rule_for_line_item(item):
    """Best-matching plan rule for one bill line item (retrieval only, no LLM call). Shown next to
    the A6 explanation so the patient sees the rule behind a flag. Returns a Hit or None."""
    network = "out-of-network" if item.bill.provider.network_status == "OUT" else "in-network"
    query = f"{guardrails.clean_text(item.description)} from an {network} provider: what do I pay?"
    try:
        found = retrieval.search(query, item.bill.insurance_plan, k=1)
    except Exception:  # the explain page must never fail because of the side panel
        log.exception("Plan-rule lookup failed for line item %s", item.pk)
        return None
    return found.hits[0] if found.hits else None
