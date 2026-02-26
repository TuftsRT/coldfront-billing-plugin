from django.urls import path

from . import views
from .views.allocation import UpdateAllocationDetailsView

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
        name='update-allocation-details',
    ),
]
