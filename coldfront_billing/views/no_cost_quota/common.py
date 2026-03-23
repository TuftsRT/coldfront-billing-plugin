from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce

from coldfront_billing.models import NoCostQuota

quota_with_remaining = NoCostQuota.objects.annotate(
    used=Coalesce(Sum('allotments__amount'), Value(0.0)),
    used_inactive=Coalesce(
        Sum(
            'allotments__amount',
            filter=~Q(allotments__allocation__status__name='Active'),
        ),
        Value(0.0),
    ),
).annotate(
    remaining=F('amount') - F('used'),
    remaining_inactive=F('amount') - F('used_inactive'),
)
