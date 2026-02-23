from django.urls import path

from . import views
from .views.allocation import UpdateStorageQuotaView

urlpatterns = [
    path('billing/', views.BillingView.as_view(), name='billing_index'),
    path(
        'cost-center-assignment/update/',
        views.CostCenterAssignmentUpdateView.as_view(),
        name='update_cost_center_assignment',
    ),
    path(
        'allocation/<int:pk>/update-storage-quota/',
        UpdateStorageQuotaView.as_view(),
        name='update-storage-quota',
    ),
]
