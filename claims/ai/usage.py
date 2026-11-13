"""P1 analytics: measure every AI request and store it as an AIRequestLog row.

    with usage.track() as u:        # collects tokens from every local_llm.generate call in the block
        ...run the feature...
    usage.log_request(request, "ask", status=..., usage=u, ...)

Logging must never break a page: log_request swallows and logs its own errors.
"""
import contextvars
import logging
import re
from contextlib import contextmanager

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

_current = contextvars.ContextVar("ai_usage", default=None)

# Ordered: the first matching topic wins ("out-of-network ER prices" is an emergency question, not a cost one).
TOPICS = [
    ("Emergency & urgent care", r"\b(emergenc\w*|er|ambulance|urgent care|surprise)\b"),
    ("Appeals & denials", r"\b(appeal\w*|denied|denial|deny|reject\w*)\b"),
    ("Preventive care", r"\b(preventive|physical|check-?up|screening|vaccin\w*|flu shots?|annual|yearly)\b"),
    ("Coverage of services", r"\b(dental|drugs?|prescription\w*|therapy|counseling|mental|acupuncture|vision|"
                             r"prior authori[sz]ation|covers?|covered)\b"),
    ("Network & referrals", r"\b(network|specialist\w*|referr\w*|provider\w*|doctor\w*|hmo|epo|ppo)\b"),
    ("Deductible & costs", r"\b(deductible|coinsurance|co-?pay\w*|out-of-pocket|oop|cost\w*|pay|owe|price\w*|premium)\b"),
    ("Billing errors", r"\b(error\w*|mistake\w*|duplicate|twice|itemi[sz]ed|code\w*|overcharg\w*)\b"),
]
TOPIC_NAMES = [name for name, _ in TOPICS] + ["Other / off-topic"]


def topic_for(question):
    text = (question or "").lower()
    for name, pattern in TOPICS:
        if re.search(pattern, text):
            return name
    return "Other / off-topic"


@contextmanager
def track():
    """Collect token counts and generation time from local_llm.generate calls inside the block."""
    stats = {"prompt_tokens": 0, "completion_tokens": 0, "llm_calls": 0, "generation_s": 0.0}
    token = _current.set(stats)
    try:
        yield stats
    finally:
        _current.reset(token)


def add(prompt_tokens, completion_tokens, seconds):
    stats = _current.get()
    if stats is not None:
        stats["prompt_tokens"] += int(prompt_tokens)
        stats["completion_tokens"] += int(completion_tokens)
        stats["llm_calls"] += 1
        stats["generation_s"] += float(seconds)


def estimate_tokens(text):
    """~4 characters per token; used only where no tokenizer is available (e.g. the Gemini letter)."""
    return max(1, round(len(text or "") / 4)) if text else 0


def log_request(request, feature, *, status, total_s, usage=None, question="", plan=None, backend="",
                model_name="", cached=False, items=0, best_score=None, warnings=0, retrieval_ms=0.0,
                prompt_tokens=None, completion_tokens=None, topic=None):
    if not getattr(settings, "AI_ANALYTICS_ENABLED", True):
        return None
    try:
        from ..models import AIRequestLog
        usage = usage or {}
        user = request.user if request is not None and request.user.is_authenticated else None
        return AIRequestLog.objects.create(
            created_at=timezone.now(), feature=feature, user=user,
            plan_type=getattr(plan, "plan_type", "") or "", question=(question or "")[:300],
            topic=topic or (topic_for(question) if feature == "ask" else dict(AIRequestLog.FEATURES)[feature]),
            status=status, backend=backend, model_name=model_name, cached=cached,
            llm_calls=usage.get("llm_calls", 0), items=items, best_score=best_score, warnings=warnings,
            retrieval_ms=round(retrieval_ms or 0, 2), generation_s=round(usage.get("generation_s", 0.0), 3),
            total_s=round(total_s, 3),
            prompt_tokens=usage.get("prompt_tokens", 0) if prompt_tokens is None else prompt_tokens,
            completion_tokens=usage.get("completion_tokens", 0) if completion_tokens is None else completion_tokens,
        )
    except Exception:  # analytics must never take a page down
        log.exception("Could not log AI request")
        return None
