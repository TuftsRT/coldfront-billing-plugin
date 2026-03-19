from django.db.models import Case, F, FloatField, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from coldfront_billing.data import UNIT_TO_TB, StorageUnit
from coldfront_billing.models import NoCostQuota


def to_tb(expr):
    return Case(
        When(units='TB', then=expr),
        When(units='GB', then=expr * Value(UNIT_TO_TB[StorageUnit.GB])),
        default=expr,
        output_field=FloatField(),
    )


quota_with_remaining = NoCostQuota.objects.annotate(
    used=Coalesce(
        Sum(
            'allotments__amount',
            filter=Q(allotments__allocation__status__name='Active'),
        ),
        Value(0.0),
    ),
).annotate(
    remaining=F('amount') - F('used'),
    amount_normalized=to_tb(F('amount')),
    remaining_normalized=to_tb(F('remaining')),
)
