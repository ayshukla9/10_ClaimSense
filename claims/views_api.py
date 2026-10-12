"""Private bill APIs and one public plan catalogue aggregate."""
import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views import View

from . import summaries
from .access import visible_bills


def _serialize(request):
    qs = visible_bills(request.user).select_related("provider", "insurance_plan")
    provider = request.GET.get("provider")
    plan = request.GET.get("plan")
    since = request.GET.get("since")  # YYYY-MM-DD
    if provider:
        qs = qs.filter(provider__name__icontains=provider)
    if plan:
        qs = qs.filter(insurance_plan__name__icontains=plan)
    if since:
        qs = qs.filter(bill_date__gte=since)  # bad format raises ValidationError
    return [
        {
            "id": b.id,
            "reference_number": b.reference_number,
            "bill_date": b.bill_date.isoformat(),
            "provider": b.provider.name,
            "plan": b.insurance_plan.name,
        }
        for b in qs
    ]


def _bad_date():
    return JsonResponse({"error": "since must be YYYY-MM-DD"}, status=400)


def api_bills(request):
    """FBV -> JsonResponse (Content-Type: application/json)."""
    try:
        data = _serialize(request)
    except ValidationError:
        return _bad_date()
    return JsonResponse({"count": len(data), "bills": data})


def api_bills_plain(request):
    """FBV -> HttpResponse (Content-Type: text/html) for the MIME comparison."""
    try:
        data = _serialize(request)
    except ValidationError:
        return _bad_date()
    return HttpResponse(json.dumps({"count": len(data), "bills": data}))


class BillAPIView(View):
    """CBV version of the JSON endpoint."""

    def get(self, request):
        try:
            data = _serialize(request)
        except ValidationError:
            return _bad_date()
        return JsonResponse({"count": len(data), "bills": data})


# ---- P1-A4 Part 1: summary endpoints for the Vega-Lite charts ----
def api_summary_providers(request):
    """One row per provider. Plain list (safe=False) because Vega-Lite wants an array."""
    return JsonResponse(summaries.provider_summary(request.user), safe=False)


def api_summary_bills(request):
    """One row per bill, oldest first."""
    return JsonResponse(summaries.bill_summary(request.user), safe=False)


from django.db.models import Count
from django.views.decorators.http import require_GET
from .models import InsurancePlan


@require_GET
def public_plan_types(request):
    """Public catalogue counts, with no patient/bill identifiers or amounts."""
    rows = list(InsurancePlan.objects.order_by("plan_type")
                .values("plan_type").annotate(plan_count=Count("pk")))
    response = JsonResponse(rows, safe=False)
    # Enables external browser consumers and the Vega Editor; this API is read-only.
    response["Access-Control-Allow-Origin"] = "*"
    return response
