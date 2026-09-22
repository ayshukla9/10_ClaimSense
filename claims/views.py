"""
P1-A2 Section 2: four view styles against the same model (Bill).

All four render the same claims/bill_list.html template -- deliberately,
per the assignment's encouragement to reuse templates across views and
demonstrate separation of concerns between "how the view gets its data"
and "how the data is displayed".
"""

from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import ListView

from .models import Bill


def bill_list_manual(request):
    """
    FBV View 1 -- HttpResponse (manual).

    Loads the template by hand with loader.get_template() and wraps the
    rendered string in an HttpResponse ourselves, instead of using the
    render() shortcut.
    """
    template = loader.get_template("claims/bill_list.html")
    context = {
        "bills": Bill.objects.all(),
        "view_label": "View 1: HttpResponse (manual, loader.get_template)",
    }
    return HttpResponse(template.render(context, request))


def bill_list_render(request):
    """
    FBV View 2 -- render() shortcut.

    Queries the model and passes the queryset into a context dict, then
    lets render() handle template loading + HttpResponse wrapping.
    """
    bills = Bill.objects.all()
    context = {
        "bills": bills,
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
        bills = Bill.objects.all()
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
    extra_context = {"view_label": "View 4: Generic CBV (ListView)"}
