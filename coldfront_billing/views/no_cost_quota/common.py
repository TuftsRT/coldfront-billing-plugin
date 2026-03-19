from django.db.models import F, FloatField, Q, Sum, Value
from django.db.models.functions import Coalesce

from coldfront_billing.models import NoCostQuota

quota_with_remaining = NoCostQuota.objects.annotate(
    used=Coalesce(
        Sum(
            'allotments__amount',
            filter=Q(allotments__allocation__status__name='Active'),
        ),
        Value(0, output_field=FloatField()),
    ),
).annotate(remaining=F('amount') - F('used'))
