"""A6: AI features on a bill.

1. Local Hugging Face model (claims/ai/local_llm.py) explains every line item in plain English.
2. Google Gemini (claims/ai/gemini_client.py) drafts an appeal letter for the flagged items.
Both run only on bills the signed-in user may already see (visible_bills).
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .access import visible_bills
from .ai import gemini_client, guardrails, local_llm

log = logging.getLogger(__name__)

MAX_ITEMS = 10  # bounds CPU time per request


def _bill(request, pk):
    return get_object_or_404(visible_bills(request.user).select_related("provider", "insurance_plan"), pk=pk)


def _explanations(bill):
    """Returns (rows, notice). Without a local model the rule checks still run, and notice says why."""
    items = list(bill.line_items.select_related("bill__provider")[:MAX_ITEMS])
    try:
        return [(item, local_llm.explain_line_item(item)) for item in items], ""
    except local_llm.LocalModelUnavailable as exc:
        return [(item, local_llm.rules_only(item)) for item in items], str(exc)


@require_http_methods(["GET", "POST"])
def bill_explain(request, pk):
    """GET shows the page; POST runs the local model (slow on CPU, so never on a plain GET)."""
    bill = _bill(request, pk)
    ctx = {"bill": bill, "model_name": settings.LOCAL_LLM_MODEL, "max_items": MAX_ITEMS,
           "gemini_ready": bool(settings.GEMINI_API_KEY)}
    if request.method == "POST":
        ctx["rows"], ctx["notice"] = _explanations(bill)
    return render(request, "claims/bill_explain.html", ctx)


def _over_limit(user):
    key = f"a6-gemini-calls:{user.pk}"
    calls = cache.get_or_set(key, 0, 60 * 60)
    if calls >= settings.GEMINI_HOURLY_LIMIT:
        return True
    cache.incr(key)
    return False


@require_http_methods(["POST"])
def bill_appeal(request, pk):
    bill = _bill(request, pk)
    ctx = {"bill": bill, "gemini_model": settings.GEMINI_MODEL}
    status = 200
    chosen = set(request.POST.getlist("items"))
    try:
        note = guardrails.check_note(request.POST.get("note", ""))
        if not chosen:  # checked before the model runs, so an empty form costs no CPU
            raise guardrails.UnsafeInput("Pick at least one line item to appeal.")
        rows, _ = _explanations(bill)  # works with or without the local model
        flagged = [(item, info) for item, info in rows if str(item.pk) in chosen]
        if not flagged:
            raise guardrails.UnsafeInput("Pick at least one line item to appeal.")
        if _over_limit(request.user):
            ctx["error"] = f"Limit of {settings.GEMINI_HOURLY_LIMIT} letters per hour reached. Try again later."
            status = 429
        else:
            ctx["prompt"] = gemini_client.build_prompt(bill, flagged, note)
            ctx["letter"] = gemini_client.draft_appeal(bill, flagged, note)
    except guardrails.UnsafeInput as exc:
        ctx["error"], status = str(exc), 400
    except gemini_client.GeminiUnavailable as exc:
        ctx["error"], status = str(exc), 503
    except Exception:  # network errors, quota, API changes: never a 500 page
        log.exception("Gemini appeal failed for bill %s", bill.pk)
        ctx["error"], status = "The Gemini API request failed. Please try again in a minute.", 502
    return render(request, "claims/bill_appeal.html", ctx, status=status)
