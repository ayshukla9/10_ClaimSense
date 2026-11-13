"""AI features.

1. A6: local Hugging Face model (claims/ai/local_llm.py) explains every line item in plain English.
2. A9: each line item also shows the closest plan rule (claims/ai/retrieval.py, no LLM call).
3. A9: "Ask about my plan" answers questions from plan documents (claims/ai/rag.py, local models only).
4. A6 (optional, secondary): Google Gemini drafts an appeal letter for the flagged items.
Everything runs only on bills and plans the signed-in user may already see.
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .access import visible_bills
from .ai import gemini_client, guardrails, local_llm, rag, usage
from .models import InsurancePlan

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
        start = time.perf_counter()
        with usage.track() as used:
            rows, ctx["notice"] = _explanations(bill)
        # A9: attach the closest plan rule to each line item (retrieval only; never breaks the page).
        ctx["rows"] = [(item, {**info, "plan_rule": rag.rule_for_line_item(item)}) for item, info in rows]
        sources = {info.get("source") for _, info in rows}
        status = "model_off" if ctx["notice"] else "fallback" if "fallback" in sources else "ok"
        usage.log_request(request, "explain", status=status, total_s=time.perf_counter() - start, usage=used,
                          plan=bill.insurance_plan, backend="rules" if ctx["notice"] else "model",
                          model_name="" if ctx["notice"] else settings.LOCAL_LLM_MODEL, items=len(rows),
                          cached=bool(rows) and not ctx["notice"] and used["llm_calls"] == 0)
        flagged = [item for item, info in rows if info.get("flag") == "review"]
        ctx["flagged_count"] = len(flagged)
        ctx["flagged_owed"] = sum((item.estimated_patient_responsibility for item in flagged), 0)
    return render(request, "claims/bill_explain.html", ctx)


def _over_limit(user, name="gemini", limit=None):
    key = f"a6-{name}-calls:{user.pk}"
    limit = settings.GEMINI_HOURLY_LIMIT if limit is None else limit
    calls = cache.get_or_set(key, 0, 60 * 60)
    if calls >= limit:
        return True
    cache.incr(key)
    return False


EXAMPLE_QUESTIONS = [
    "I went to an out-of-network emergency room. Do I have to pay out-of-network prices?",
    "What is my deductible and what do I pay after I meet it?",
    "Can I see a specialist outside my network?",
    "How long do I have to appeal a denied claim?",
    "Is my yearly physical free before I meet my deductible?",
]


def _plans_for(user):
    """Staff can ask about any plan; a patient only about their own; anyone else gets general rules."""
    if user.is_staff:
        return list(InsurancePlan.objects.all())
    patient = getattr(user, "patient_record", None)
    return [patient.insurance_plan] if patient else []


@require_http_methods(["GET", "POST"])
def ask_plan(request):
    """A9: question -> plan-filtered retrieval -> local LLM answer with citations.
    GET shows the form; the models only run on POST."""
    plans = _plans_for(request.user)
    chosen = request.POST.get("plan") or request.GET.get("plan")
    plan = next((p for p in plans if str(p.pk) == str(chosen)), plans[0] if plans else None)
    ctx = {"plans": plans, "plan": plan, "examples": EXAMPLE_QUESTIONS,
           "max_chars": guardrails.MAX_QUESTION_CHARS, "model_name": settings.LOCAL_LLM_MODEL,
           "embedding_model": settings.EMBEDDING_MODEL, "question": request.GET.get("q", "")[:500]}
    status = 200
    if request.method == "POST":
        ctx["question"] = request.POST.get("question", "")[:2000]
        start, answer, used, outcome = time.perf_counter(), None, None, "error"
        try:
            guardrails.check_question(ctx["question"])  # validate before counting toward the limit
            if _over_limit(request.user, "rag", settings.RAG_HOURLY_LIMIT):
                ctx["error"], status = f"Limit of {settings.RAG_HOURLY_LIMIT} questions per hour reached.", 429
                outcome = "rate_limited"
            else:
                with usage.track() as used:
                    answer = ctx["answer"] = rag.answer_question(ctx["question"], plan)
                outcome = answer.status
        except guardrails.UnsafeInput as exc:
            ctx["error"], status, outcome = str(exc), 400, "rejected"
        except Exception:  # model crash, out of memory, corrupt cache: never a 500 page
            log.exception("Plan question failed")
            ctx["error"], status = "Something went wrong while answering. Please try again.", 503
        _log_question(request, plan, ctx["question"], outcome, answer, used, time.perf_counter() - start)
    return render(request, "claims/ask_plan.html", ctx, status=status)


def _log_question(request, plan, question, outcome, answer, used, seconds):
    """One analytics row per question, whatever happened (rejected and rate-limited questions included)."""
    extra = {}
    if answer is not None:
        extra = {"backend": answer.backend, "cached": answer.cached, "best_score": round(answer.best_score, 3),
                 "warnings": len(answer.warnings), "retrieval_ms": answer.retrieval_ms,
                 "model_name": settings.LOCAL_LLM_MODEL if answer.llm_called or answer.cached else ""}
    usage.log_request(request, "ask", status=outcome, total_s=seconds, usage=used,
                      question=guardrails.clean_text(question, 300), plan=plan, **extra)


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
            start = time.perf_counter()
            ctx["letter"] = gemini_client.draft_appeal(bill, flagged, note)
            # Gemini's usage numbers aren't exposed by our client, so tokens are estimated (~4 chars per token).
            usage.log_request(request, "appeal", status="ok", total_s=time.perf_counter() - start,
                              usage={"llm_calls": 1, "generation_s": time.perf_counter() - start},
                              plan=bill.insurance_plan, backend="gemini", model_name=settings.GEMINI_MODEL,
                              items=len(flagged), prompt_tokens=usage.estimate_tokens(ctx["prompt"]),
                              completion_tokens=usage.estimate_tokens(ctx["letter"]))
    except guardrails.UnsafeInput as exc:
        ctx["error"], status = str(exc), 400
    except gemini_client.GeminiUnavailable as exc:
        ctx["error"], status = str(exc), 503
    except Exception:  # network errors, quota, API changes: never a 500 page
        log.exception("Gemini appeal failed for bill %s", bill.pk)
        ctx["error"], status = "The Gemini API request failed. Please try again in a minute.", 502
    return render(request, "claims/bill_appeal.html", ctx, status=status)
