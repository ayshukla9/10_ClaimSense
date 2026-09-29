"""Section 5: one CBV handling GET (filter) and POST (create)."""
from django.shortcuts import redirect
from django.views.generic import ListView

from .forms import BillForm
from .models import Bill


class BillManageView(ListView):
    model = Bill
    template_name = "claims/bill_manage.html"
    context_object_name = "bills"

    def get_queryset(self):
        qs = Bill.objects.select_related("patient", "provider")
        q = self.request.GET.get("q", "").strip()
        return qs.filter(reference_number__icontains=q) if q else qs

    def get_context_data(self, **kwargs):
        form = kwargs.pop("form", None)
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = form or BillForm()
        ctx["q"] = self.request.GET.get("q", "")
        return ctx

    def post(self, request, *args, **kwargs):
        form = BillForm(request.POST)
        if form.is_valid():
            return redirect(form.save())  # uses Bill.get_absolute_url()
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(form=form))
