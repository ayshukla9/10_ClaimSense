from django.urls import path

from . import views

app_name = "claims"

urlpatterns = [
    path("bills/manual/", views.bill_list_manual, name="bill-list-manual"),
    path("bills/render/", views.bill_list_render, name="bill-list-render"),
    path("bills/cbv-base/", views.BillListBaseView.as_view(), name="bill-list-cbv-base"),
    path("bills/cbv-generic/", views.BillListView.as_view(), name="bill-list-cbv-generic"),
]
