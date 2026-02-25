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
]
