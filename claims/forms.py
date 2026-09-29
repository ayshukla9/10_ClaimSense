from django import forms

from .models import Bill


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ["reference_number", "bill_date", "patient", "provider", "insurance_plan"]
        widgets = {"bill_date": forms.DateInput(attrs={"type": "date"})}
