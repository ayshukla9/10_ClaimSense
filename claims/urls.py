from django.urls import path
from .access import private_view

from . import (
    views,
    views_api,
    views_charts,
    views_exports,
    views_external,
    views_forms,
    views_ai,
    views_search,
    views_vega,
)

app_name = "claims"

urlpatterns = [
    # Pages
    path("", views.HomeView.as_view(), name="home"),
    path("bills/<int:pk>/", views.BillDetailView.as_view(), name="bill-detail"),
    path("bills/<int:pk>/explain/", views_ai.bill_explain, name="bill-explain"),
    path("bills/<int:pk>/appeal/", views_ai.bill_appeal, name="bill-appeal"),
    path("bills/manual/", views.bill_list_manual, name="bill-list-manual"),
    path("bills/render/", views.bill_list_render, name="bill-list-render"),
    path("bills/cbv-base/", views.BillListBaseView.as_view(), name="bill-list-cbv-base"),
    path("bills/cbv-generic/", views.BillListView.as_view(), name="bill-list-cbv-generic"),
    path("bills/search/", views_search.bill_search, name="bill-search"),
    path("bills/lookup/", views_search.bill_lookup, name="bill-lookup"),
    path("bills/summary/", views_search.bill_summary, name="bill-summary"),
    path("bills/manage/", views_forms.BillManageView.as_view(), name="bill-manage"),
    path("procedures/", views_external.procedure_lookup, name="procedure-lookup"),
    # Reports and exports
    path("reports/", views_exports.reports, name="reports"),
    path("exports/bills.csv", views_exports.export_bills_csv, name="export-bills-csv"),
    path("exports/bills.json", views_exports.export_bills_json, name="export-bills-json"),
    # Charts
    path("charts/", views_charts.charts_page, name="charts"),
    path("charts/bills-per-provider.png", views_charts.bills_per_provider_png, name="chart-bills-per-provider"),
    path("vega-lite/", views_vega.vega_page, name="vega-charts"),
    path("vega-lite/<str:name>.png", views_vega.vega_chart_png, name="vega-chart-png"),
    # JSON API
    path("api/bills/", views_api.api_bills, name="api-bills"),
    path("api/bills/plain/", views_api.api_bills_plain, name="api-bills-plain"),
    path("api/bills/cbv/", views_api.BillAPIView.as_view(), name="api-bills-cbv"),
    path("api/summary/providers/", views_api.api_summary_providers, name="api-summary-providers"),
    path("api/summary/bills/", views_api.api_summary_bills, name="api-summary-bills"),
    path("api/procedures/", views_external.api_procedures, name="api-procedures"),
]

# Protect every existing records route, including exports and chart images.
# New routes are private by default. Exactly one public JSON API is appended.
for route in urlpatterns:
    if route.name != "home":
        route.callback = private_view(route.callback, staff_only=route.name == "bill-manage", api=str(route.pattern).startswith("api/") or route.name == "export-bills-json")
urlpatterns += [path("api/public/plan-types/", views_api.public_plan_types, name="public-plan-types")]
