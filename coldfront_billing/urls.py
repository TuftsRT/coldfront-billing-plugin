from django.urls import path

from . import views

urlpatterns = [
    path('billing/', views.BillingView.as_view(), name='billing_index'),
    path(
        'cost-center-assignment/update/',
        views.CostCenterAssignmentUpdateView.as_view(),
        name='update_cost_center_assignment',
    ),
]
