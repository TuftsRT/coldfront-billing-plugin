from django.urls import path

from . import views
from .views.allocation import UpdateAllocationDetailsView
from .views.no_cost_quota import (
    AssignNoCostQuotasView,
    CreateNoCostQuotaAllotmentView,
    ManageNoCostQuotasView,
)

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
        'allocation/<int:pk>/update-allocation-details/',
        UpdateAllocationDetailsView.as_view(),
        name='update_allocation_details',
    ),
    path(
        'no-cost-quota/manage/',
        ManageNoCostQuotasView.as_view(),
        name='manage_no_cost_quota',
    ),
    path(
        'no-cost-quota/assign/',
        AssignNoCostQuotasView.as_view(),
        name='assign_no_cost_quota',
    ),
    path(
        'no-cost-quota/allotment/create/',
        CreateNoCostQuotaAllotmentView.as_view(),
        name='create_no_cost_quota_allotment',
    ),
]
