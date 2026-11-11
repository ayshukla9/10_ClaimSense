"""Phase 2 UI: per-bill totals and rule-check flags for the dashboard, bill list and bill detail.

Flags come from the same deterministic rule_checks() the AI explain page uses, so a charge that
shows "Needs review" here is flagged there too. No model is loaded.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from .ai.guardrails import rule_checks

ZERO = Decimal("0")

# Short labels for the badges; the full sentence from rule_checks() is kept for tooltips/details.
ISSUE_LABELS = {
    "Provider is out of network.": "Out of network",
    "Patient pays half or more of this charge.": "High patient share",
    "Covered plus patient share does not add up to the charge.": "Totals don't add up",
}


def issue_label(issue):
    return ISSUE_LABELS.get(issue, issue.rstrip("."))


@dataclass
class BillRow:
    bill: object
    charged: Decimal = ZERO
    covered: Decimal = ZERO
    owed: Decimal = ZERO
    item_count: int = 0
    flagged_items: int = 0
    issues: list = field(default_factory=list)  # unique short labels, in first-seen order

    @property
    def needs_review(self):
        return bool(self.issues)

    @property
    def out_of_network(self):
        return self.bill.provider.network_status == "OUT"


def bill_rows(bills):
    """Turn a Bill queryset into BillRow objects (2 queries: bills + line items)."""
    bills = bills.select_related("patient", "provider", "insurance_plan").prefetch_related("line_items")
    rows = []
    for bill in bills:
        row = BillRow(bill=bill)
        for item in bill.line_items.all():
            row.item_count += 1
            row.charged += item.charged_amount
            row.covered += item.estimated_covered_amount
            row.owed += item.estimated_patient_responsibility
            issues = rule_checks(item)
            if issues:
                row.flagged_items += 1
            for issue in issues:
                label = issue_label(issue)
                if label not in row.issues:
                    row.issues.append(label)
        rows.append(row)
    return rows


def line_item_flags(items):
    """[(item, [short labels])] for a bill's line items."""
    return [(item, [issue_label(i) for i in rule_checks(item)]) for item in items]


def dashboard_stats(rows):
    return {
        "bill_count": len(rows),
        "charged": sum((r.charged for r in rows), ZERO),
        "covered": sum((r.covered for r in rows), ZERO),
        "owed": sum((r.owed for r in rows), ZERO),
        "flagged_items": sum(r.flagged_items for r in rows),
        "flagged_bills": sum(1 for r in rows if r.needs_review),
        "out_of_network_bills": sum(1 for r in rows if r.out_of_network),
    }


def filter_rows(rows, *, q="", network="", flagged=False, sort="date"):
    """Search and filter for the Bills page. Done in Python because the rows are already loaded
    and a patient has a handful of bills; staff lists are small in this project too."""
    if q:
        needle = q.lower()
        rows = [
            r for r in rows
            if needle in r.bill.reference_number.lower()
            or needle in r.bill.provider.name.lower()
            or needle in r.bill.patient.name.lower()
            or any(needle in li.description.lower() for li in r.bill.line_items.all())
        ]
    if network in ("IN", "OUT"):
        rows = [r for r in rows if r.bill.provider.network_status == network]
    if flagged:
        rows = [r for r in rows if r.needs_review]
    if sort == "owed":
        rows = sorted(rows, key=lambda r: r.owed, reverse=True)
    elif sort == "oldest":
        rows = sorted(rows, key=lambda r: (r.bill.bill_date, r.bill.reference_number))
    else:
        rows = sorted(rows, key=lambda r: (r.bill.bill_date, r.bill.reference_number), reverse=True)
    return rows
