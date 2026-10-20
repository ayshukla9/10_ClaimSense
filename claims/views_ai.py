"""P1-A6: text intelligence pages.

- ai_parse: paste bill text; a local Hugging Face model turns it into line items.
  Ticking "explain" sends the parsed result on to the large hosted model (hybrid pipeline).
- bill_explain: the hosted model (gpt-oss-120b on Groq) explains a saved bill the user may see.
"""
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .access import visible_bills
from .ai import explainer, local_parser
from .ai.guardrails import GuardrailError, clean_bill_text, injection_warnings
from .forms import BillTextForm


def _within_rate_limit(user):
    """At most AI_RATE_LIMIT model calls per user per 10 minutes (protects compute and API quota)."""
    key = f"ai-calls:{user.pk}"
    cache.add(key, 0, timeout=600)
    try:
        calls = cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, timeout=600)
        calls = 1
    return calls <= settings.AI_RATE_LIMIT


@require_http_methods(["GET", "POST"])
def ai_parse(request):
    context = {"form": BillTextForm(), "model_name": settings.LOCAL_LLM_MODEL}
    if request.method == "POST":
        form = BillTextForm(request.POST)
        context["form"] = form
        if form.is_valid():
            try:
                text = clean_bill_text(form.cleaned_data["bill_text"])
                context["warnings"] = injection_warnings(text)
                if not _within_rate_limit(request.user):
                    raise GuardrailError("You've used the AI tools a lot in the last few minutes. Please wait and try again.")
                parsed, seconds = local_parser.parse_bill(text)
                context.update(parsed=parsed, seconds=seconds)
                if form.cleaned_data["explain"]:
                    try:
                        context["explanation"] = explainer.explain(explainer.describe_parsed(parsed))
                    except explainer.AIServiceError as exc:
                        context["explain_error"] = str(exc)
            except (GuardrailError, local_parser.LocalModelUnavailable) as exc:
                context["error"] = str(exc)
    return render(request, "claims/ai_parse.html", context)


@require_http_methods(["GET", "POST"])
def bill_explain(request, pk):
    bill = get_object_or_404(
        visible_bills(request.user).select_related("provider", "insurance_plan").prefetch_related("line_items"), pk=pk,
    )
    context = {"bill": bill}
    # Only a POST spends API quota, so link prefetchers and crawlers can't trigger calls.
    if request.method == "POST":
        if not bill.line_items.exists():
            context["error"] = "This bill has no line items to explain."
        elif not _within_rate_limit(request.user):
            context["error"] = "You've used the AI tools a lot in the last few minutes. Please wait and try again."
        else:
            try:
                context["explanation"] = explainer.explain(explainer.describe_bill(bill))
            except explainer.AIServiceError as exc:
                context["error"] = str(exc)
    return render(request, "claims/bill_explain.html", context)
