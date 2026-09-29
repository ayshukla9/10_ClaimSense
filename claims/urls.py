from django.urls import path

from . import views, views_api, views_charts, views_forms, views_search

app_name = "claims"

urlpatterns = [
    # Section 1
    path("", views.HomeView.as_view(), name="home"),
    path("bills/<int:pk>/", views.BillDetailView.as_view(), name="bill-detail"),
    # P1-A2 routes
    path("bills/manual/", views.bill_list_manual, name="bill-list-manual"),
    path("bills/render/", views.bill_list_render, name="bill-list-render"),
    path("bills/cbv-base/", views.BillListBaseView.as_view(), name="bill-list-cbv-base"),
    path("bills/cbv-generic/", views.BillListView.as_view(), name="bill-list-cbv-generic"),
    # Section 2
    path("bills/search/", views_search.bill_search, name="bill-search"),
    path("bills/lookup/", views_search.bill_lookup, name="bill-lookup"),
    path("bills/summary/", views_search.bill_summary, name="bill-summary"),
    # Section 4
    path("charts/", views_charts.charts_page, name="charts"),
    path("charts/bills-per-provider.png", views_charts.bills_per_provider_png, name="chart-bills-per-provider"),
    # Section 5
    path("bills/manage/", views_forms.BillManageView.as_view(), name="bill-manage"),
    # Section 6
    path("api/bills/", views_api.api_bills, name="api-bills"),
    path("api/bills/plain/", views_api.api_bills_plain, name="api-bills-plain"),
    path("api/bills/cbv/", views_api.BillAPIView.as_view(), name="api-bills-cbv"),
]
