from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    InsurancePlan,
    Patient,
    Provider,
    Bill,
    BillLineItem,
    AIRequestLog,
)

admin.site.register(InsurancePlan)
admin.site.register(Patient)
admin.site.register(Provider)
admin.site.register(Bill)
admin.site.register(BillLineItem)

@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "feature", "status", "topic", "total_s", "prompt_tokens", "completion_tokens", "cached", "simulated")
    list_filter = ("feature", "status", "cached", "simulated", "topic")
    search_fields = ("question",)
    date_hierarchy = "created_at"
