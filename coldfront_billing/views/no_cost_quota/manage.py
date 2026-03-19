from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, QuerySet
from django.views.generic import ListView

from coldfront_billing.filters import get_no_cost_quota_ordering
from coldfront_billing.forms import NoCostQuotaSearchForm
from coldfront_billing.models import NoCostQuota
from coldfront_billing.views.mixins import PAGINATE_BY, get_pagination_params
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


class ManageNoCostQuotasView(LoginRequiredMixin, ListView):
    template_name = 'no_cost_quota/manage.html'
    context_object_name = 'quota_list'
    model = NoCostQuota
    paginate_by = PAGINATE_BY

    def filter_quotas(self, quotas: QuerySet[NoCostQuota]) -> QuerySet[NoCostQuota]:
        search_form = NoCostQuotaSearchForm(self.request.GET)
        if search_form.is_valid():
            if username := search_form.cleaned_data.get('username'):
                quotas = quotas.filter(Q(user__username__icontains=username))
        return quotas

    def get_queryset(self) -> QuerySet[NoCostQuota]:
        ordering = get_no_cost_quota_ordering(self.request.GET)
        qs = self.filter_quotas(quota_with_remaining).order_by(ordering)

        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        for quota in context.get('quota_list', []):
            if quota.used_inactive != 0:
                quota.has_inactive = True

        return context | get_pagination_params(self.request.GET)
        | {
            'search_form': NoCostQuotaSearchForm(self.request.GET),
        }
