"""
P1-A2 Section 2: four view styles against the same model (Bill).

All four render the same claims/bill_list.html template -- deliberately,
per the assignment's encouragement to reuse templates across views and
demonstrate separation of concerns between "how the view gets its data"
and "how the data is displayed".
"""

from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from .models import Bill
from .access import visible_bills
from .bill_insights import bill_rows, dashboard_stats, filter_rows, line_item_flags


def bill_list_manual(request):
    """
    FBV View 1 -- HttpResponse (manual).

    Loads the template by hand with loader.get_template() and wraps the
    rendered string in an HttpResponse ourselves, instead of using the
    render() shortcut.
    """
    template = loader.get_template("claims/bill_list.html")
    context = {
        "bills": visible_bills(request.user),
        "view_label": "View 1: HttpResponse (manual, loader.get_template)",
    }
    return HttpResponse(template.render(context, request))


def bill_list_render(request):
    """
    FBV View 2 -- render() shortcut.

    Queries the model and passes the queryset into a context dict, then
    lets render() handle template loading + HttpResponse wrapping.
    """
    bills = visible_bills(request.user)
    filters = {
        "q": request.GET.get("q", "").strip()[:100],
        "network": request.GET.get("network", ""),
        "flagged": request.GET.get("flagged") == "1",
        "sort": request.GET.get("sort", "date"),
    }
    all_rows = bill_rows(bills)
    rows = filter_rows(all_rows, **filters)
    context = {
        "bills": bills,
        "rows": rows,
        "total_count": len(all_rows),
        "filters": filters,
        "filtering": bool(filters["q"] or filters["network"] or filters["flagged"]),
        "view_label": "View 2: render() shortcut",
    }
    return render(request, "claims/bill_list.html", context)


class BillListBaseView(View):
    """
    CBV View 3 -- base View (django.views.View).

    Same query + template as View 2, but expressed as a class with an
    explicit get() handler instead of a plain function.
    """

    def get(self, request):
        bills = visible_bills(request.user)
        context = {
            "bills": bills,
            "view_label": "View 3: Base CBV (django.views.View)",
        }
        return render(request, "claims/bill_list.html", context)


class BillListView(ListView):
    """
    CBV View 4 -- generic CBV (ListView).

    Django handles the queryset (model = Bill) and template resolution;
    template_name and context_object_name are set explicitly so this
    reuses the exact same template as the other three views.
    """

    model = Bill
    template_name = "claims/bill_list.html"
    context_object_name = "bills"
    def get_queryset(self):
        return visible_bills(self.request.user)

    extra_context = {"view_label": "View 4: Generic CBV (ListView)"}


# ---- P1-A3 Section 1: home + detail ----
class HomeView(TemplateView):
    template_name = "claims/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            from .views_ai import EXAMPLE_QUESTIONS, _plans_for

            rows = bill_rows(visible_bills(user))
            ctx["rows"] = rows
            ctx["stats"] = dashboard_stats(rows)
            ctx["attention"] = sorted((r for r in rows if r.needs_review), key=lambda r: r.owed, reverse=True)[:4]
            ctx["recent_rows"] = rows[:5]  # Bill.Meta.ordering is newest first
            ctx["total_bills"] = len(rows)
            plans = _plans_for(user)
            ctx["plan"] = plans[0] if len(plans) == 1 else None
            ctx["example_questions"] = EXAMPLE_QUESTIONS[:3]
            ctx["display_name"] = getattr(getattr(user, "patient_record", None), "name", "") or user.get_full_name() or user.username
        return ctx


class BillDetailView(DetailView):
    model = Bill
    template_name = "claims/bill_detail.html"
    def get_queryset(self):
        return visible_bills(self.request.user).select_related("patient", "provider", "insurance_plan")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["line_items"] = self.object.line_items.all()
        ctx["item_flags"] = line_item_flags(ctx["line_items"])
        ctx["flagged_count"] = sum(1 for _, flags in ctx["item_flags"] if flags)
        ctx["flag_labels"] = list(dict.fromkeys(f for _, flags in ctx["item_flags"] for f in flags))
        ctx["totals"] = self.object.line_items.aggregate(
            charged=Sum("charged_amount"),
            covered=Sum("estimated_covered_amount"),
            patient=Sum("estimated_patient_responsibility"),
        )
        return ctx


# ---- UI plan Phase 4: one page linking every course-assignment view and API ----
class DeveloperView(TemplateView):
    template_name = "claims/developer.html"
