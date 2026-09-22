from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    InsurancePlan,
    Patient,
    Provider,
    Bill,
    BillLineItem,
)

admin.site.register(InsurancePlan)
admin.site.register(Patient)
admin.site.register(Provider)
admin.site.register(Bill)
admin.site.register(BillLineItem)