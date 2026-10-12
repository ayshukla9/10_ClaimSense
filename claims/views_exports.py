"""P1-A4 Part 3: CSV + JSON export of bills, and the reports page."""
import csv

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from . import summaries

# CSV columns; exports use the same ownership scope as pages and APIs.
EXPORT_FIELDS = [
    "reference_number",
    "bill_date",
    "provider",
    "network_status",
    "plan",
    "total_charged",
    "total_covered",
    "patient_responsibility",
]


def _filename(extension):
    return f"bills_{timezone.now():%Y-%m-%d_%H-%M}.{extension}"


def export_bills_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{_filename("csv")}"'
    writer = csv.DictWriter(response, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(summaries.bill_summary(request.user))
    return response


def export_bills_json(request):
    bills = summaries.bill_summary(request.user)
    payload = {
        "generated_at": timezone.now().isoformat(),
        "record_count": len(bills),
        "bills": bills,
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{_filename("json")}"'
    return response


def reports(request):
    bills = summaries.bill_summary(request.user)
    ctx = {
        "per_provider": summaries.provider_summary(request.user),
        "per_network": summaries.network_summary(bills),
        "totals": summaries.totals(bills),
    }
    return render(request, "claims/reports.html", ctx)
