"""P1-A4: totals per provider / per bill. Used by the API, the charts, the reports page and exports."""
from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce

from .models import Bill, Provider

AMOUNT_KEYS = ("total_charged", "total_covered", "patient_responsibility")


def _money(prefix=""):
    # the three Sum()s we need everywhere; Coalesce so a bill with no line items gives 0, not None
    path = f"{prefix}line_items__"
    fields = ("charged_amount", "estimated_covered_amount", "estimated_patient_responsibility")
    return {
        key: Coalesce(Sum(path + field), 0, output_field=DecimalField())
        for key, field in zip(AMOUNT_KEYS, fields)
    }


def provider_summary():
    """One row per provider."""
    qs = Provider.objects.annotate(
        bill_count=Count("bills", distinct=True), **_money("bills__")
    ).order_by("name")
    return [
        {
            "provider": p.name,
            "network_status": p.get_network_status_display(),
            "bill_count": p.bill_count,
            "total_charged": float(p.total_charged),
            "total_covered": float(p.total_covered),
            "patient_responsibility": float(p.patient_responsibility),
        }
        for p in qs
    ]


def bill_summary():
    """One row per bill, oldest first (for the line chart)."""
    qs = (
        Bill.objects.select_related("provider", "insurance_plan")
        .annotate(**_money())
        .order_by("bill_date", "reference_number")
    )
    return [
        {
            "reference_number": b.reference_number,
            "bill_date": b.bill_date.isoformat(),
            "provider": b.provider.name,
            "network_status": b.provider.get_network_status_display(),
            "plan": b.insurance_plan.name,
            "total_charged": float(b.total_charged),
            "total_covered": float(b.total_covered),
            "patient_responsibility": float(b.patient_responsibility),
        }
        for b in qs
    ]


def network_summary(bills):
    """In network vs out of network. Takes the rows from bill_summary()."""
    groups = {}
    for row in bills:
        group = groups.setdefault(
            row["network_status"],
            {"network_status": row["network_status"], "bill_count": 0, **dict.fromkeys(AMOUNT_KEYS, 0.0)},
        )
        group["bill_count"] += 1
        for key in AMOUNT_KEYS:
            group[key] += row[key]
    return sorted(groups.values(), key=lambda g: g["network_status"])


def totals(bills):
    """Totals line for the reports page."""
    return {
        "bill_count": len(bills),
        **{key: sum(row[key] for row in bills) for key in AMOUNT_KEYS},
    }
