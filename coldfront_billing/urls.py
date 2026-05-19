from django.urls import path

from . import views

urlpatterns = [
    path('billing/', views.BillingView.as_view(), name='billing_index'),
    path(
        'billing/<int:project_id>/',
        views.BillingDetailsView.as_view(),
        name='billing_details',
    ),
    path(
        'cost-center-assignment/update/',
        views.CostCenterAssignmentUpdateView.as_view(),
        name='update_cost_center_assignment',
    ),
    path(
        'cost-center-autocomplete',
        views.CostCenterAutocompleteView.as_view(),
        name='autocomplete_cost_center',
    ),
    path(
        'allocation/<int:pk>/update-allocation-details/',
        views.UpdateAllocationDetailsView.as_view(),
        name='update_allocation_details',
    ),
    path(
        'allocation/<int:pk>/allocation-cost-preview/',
        views.AllocationCostPreviewView.as_view(),
        name='allocation_cost_preview',
    ),
    path(
        'no-cost-quota/manage/',
        views.ManageNoCostQuotasView.as_view(),
        name='manage_no_cost_quota',
    ),
    path(
        'no-cost-quota/assign/',
        views.AssignNoCostQuotasView.as_view(),
        name='assign_no_cost_quota',
    ),
    path(
        'no-cost-quota/allotment/manage/',
        views.ManageAllotmentView.as_view(),
        name='no_cost_quota_manage_allotment',
    ),
    path(
        'no-cost-quota/allotment/auto/',
        views.AutoAssignAllotmentsView.as_view(),
        name='no_cost_quota_auto_allotment',
    ),
    path('billing/reports/export', views.ExportBillingReportView.as_view(), name='reports_export'),
    path('billing/reports/manage', views.ManageReportsView.as_view(), name='reports_manage'),
    path(
        'billing/reports/history',
        views.BillingScheduleHistoryListView.as_view(),
        name='reports_billing_history',
    ),
    path('billing/reports/send', views.SendReportView.as_view(), name='reports_send'),
]
