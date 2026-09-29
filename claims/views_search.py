"""Section 2: GET search, POST lookup, relationship spanning, aggregations."""
from django.db.models import Count, Sum
from django.shortcuts import render

from .models import Bill, Provider


def _bills():
    return Bill.objects.select_related("patient", "provider")


def bill_search(request):
    """GET: same URL + query string always returns the same results (shareable)."""
    q = request.GET.get("provider", "").strip()
    bills = _bills()
    if q:
        bills = bills.filter(provider__name__icontains=q)  # relationship spanning
    return render(request, "claims/bill_search.html", {"bills": bills, "q": q})


def bill_lookup(request):
    """POST: patient email stays out of the URL, browser history and server logs."""
    bills, email = None, ""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        bills = _bills().filter(patient__email__iexact=email)  # relationship spanning
    return render(request, "claims/bill_lookup.html", {"bills": bills, "email": email})


def bill_summary(request):
    ctx = {
        "bills": _bills(),
        "total_bills": Bill.objects.count(),
        "per_provider": Provider.objects.annotate(n=Count("bills")).order_by("-n", "name"),
        "bill_totals": _bills().annotate(total=Sum("line_items__charged_amount")),
    }
    return render(request, "claims/bill_summary.html", ctx)
