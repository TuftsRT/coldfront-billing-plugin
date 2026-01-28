from django.urls import path

from . import views

urlpatterns = [
    path('b-link/', views.b_link, name='billing_b_link'),
    path('billing/', views.BillingView.as_view(), name='billing_index'),
]
