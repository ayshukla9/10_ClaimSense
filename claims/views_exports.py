"""P1-A4 Part 3: CSV + JSON export of bills, and the reports page."""
import csv

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from . import summaries

# CSV columns. No patient name/email for now -- anyone can download this
# until we add login in A5.
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
    writer.writerows(summaries.bill_summary())
    return response


def export_bills_json(request):
    bills = summaries.bill_summary()
    payload = {
        "generated_at": timezone.now().isoformat(),
        "record_count": len(bills),
        "bills": bills,
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{_filename("json")}"'
    return response


def reports(request):
    bills = summaries.bill_summary()
    ctx = {
        "per_provider": summaries.provider_summary(),
        "per_network": summaries.network_summary(bills),
        "totals": summaries.totals(bills),
    }
    return render(request, "claims/reports.html", ctx)
