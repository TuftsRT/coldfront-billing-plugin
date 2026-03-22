from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.views.generic import ListView

from coldfront_billing.models import NoCostQuota
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


class ManageNoCostQuotasView(LoginRequiredMixin, ListView):
    template_name = 'no_cost_quota/manage.html'
    context_object_name = 'quota_list'
    model = NoCostQuota

    def get_queryset(self) -> QuerySet[NoCostQuota]:
        qs = quota_with_remaining.order_by('user__username', 'quota_type')

        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        for quota in context.get('quota_list', []):
            if quota.used_inactive != 0:
                quota.has_inactive = True

        return context
