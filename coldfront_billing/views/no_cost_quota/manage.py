from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.views.generic import ListView

from coldfront_billing.models import NoCostQuota
from coldfront_billing.views.no_cost_quota.common import remaining_quota


class ManageNoCostQuotasView(LoginRequiredMixin, ListView):
    template_name = 'no_cost_quota/manage.html'
    context_object_name = 'quota_list'
    model = NoCostQuota

    def get_queryset(self) -> QuerySet[NoCostQuota]:
        qs = remaining_quota.order_by('user__username', 'quota_type')

        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)

        return qs
