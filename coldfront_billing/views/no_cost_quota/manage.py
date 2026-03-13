from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, FloatField, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.views.generic import ListView

from coldfront_billing.models import NoCostQuota


class ManageNoCostQuotasView(LoginRequiredMixin, ListView):
    template_name = 'no_cost_quota/manage.html'
    context_object_name = 'quota_list'
    model = NoCostQuota

    def get_queryset(self) -> QuerySet[NoCostQuota]:
        qs = (
            NoCostQuota.objects.select_related('user')
            .annotate(
                used=Coalesce(Sum('allotments__amount'), Value(0, output_field=FloatField())),
            )
            .annotate(
                remaining=F('amount') - F('used'),
            )
            .order_by('user__username', 'quota_type')
        )

        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)

        return qs
