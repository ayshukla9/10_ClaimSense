"""Section 2: GET search, POST lookup, relationship spanning, aggregations."""
from django.db.models import Count, Sum, Q
from django.shortcuts import render

from .access import visible_bills, visible_providers


def _bills(user):
    return visible_bills(user).select_related("patient", "provider")


def bill_search(request):
    """GET: same URL + query string always returns the same results (shareable)."""
    q = request.GET.get("provider", "").strip()
    bills = _bills(request.user)
    if q:
        bills = bills.filter(provider__name__icontains=q)  # relationship spanning
    return render(request, "claims/bill_search.html", {"bills": bills, "q": q})


def bill_lookup(request):
    """POST: patient email stays out of the URL, browser history and server logs."""
    bills, email = None, ""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        bills = _bills(request.user).filter(patient__email__iexact=email)  # relationship spanning
    return render(request, "claims/bill_lookup.html", {"bills": bills, "email": email})


def bill_summary(request):
    ctx = {
        "bills": _bills(request.user),
        "total_bills": visible_bills(request.user).count(),
        "per_provider": visible_providers(request.user).annotate(n=Count("bills", filter=Q(bills__in=visible_bills(request.user)))).order_by("-n", "name"),
        "bill_totals": _bills(request.user).annotate(total=Sum("line_items__charged_amount")),
    }
    return render(request, "claims/bill_summary.html", ctx)
