from django.db.models import Case, F, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from coldfront_billing.data import UNIT_TO_TB
from coldfront_billing.enums import AllocationStatus, StorageUnit
from coldfront_billing.models import NoCostQuota


def to_tb(expr):
    return Case(
        When(units='TB', then=expr),
        When(units='GB', then=expr * Value(UNIT_TO_TB[StorageUnit.GB])),
        default=expr,
        output_field=DecimalField(),
    )


quota_with_remaining = NoCostQuota.objects.annotate(
    used=Coalesce(Sum('allotments__amount_tb'), Value(0.0), output_field=DecimalField()),
    used_inactive=Coalesce(
        Sum(
            'allotments__amount_tb',
            filter=~Q(allotments__allocation__status__name=AllocationStatus.ACTIVE),
        ),
        Value(0.0),
        output_field=DecimalField(),
    ),
).annotate(
    remaining=F('amount_tb') - F('used'),
    remaining_inactive=F('amount_tb') - F('used_inactive'),
    amount_normalized=to_tb(F('amount_tb')),
    remaining_normalized=to_tb(F('remaining')),
)
