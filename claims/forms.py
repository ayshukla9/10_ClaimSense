from django import forms

from .models import Bill


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ["reference_number", "bill_date", "patient", "provider", "insurance_plan"]
        widgets = {"bill_date": forms.DateInput(attrs={"type": "date"})}


class BillTextForm(forms.Form):
    """P1-A6: raw bill text for the local model. Length is also re-checked after cleaning."""

    bill_text = forms.CharField(
        label="Bill text", max_length=4000, strip=True,
        widget=forms.Textarea(attrs={"rows": 10, "cols": 70, "placeholder": "Paste the text of a medical bill here"}),
    )
    explain = forms.BooleanField(label="Also explain it in plain English (gpt-oss-120b via Groq)", required=False)
