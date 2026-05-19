from coldfront.core.allocation.models import Allocation
from django.shortcuts import get_object_or_404

from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment


def create_update_allotment(allocation: Allocation, amount: float, quota: NoCostQuota, append: bool = False) -> str:
    allotment, created = NoCostQuotaAllotment.objects.get_or_create(
        no_cost_quota=quota,
        allocation=allocation,
        defaults={'amount': amount},
    )

    if not created:
        if append:
            allotment.amount += amount
        else:
            allotment.amount = amount

    try:
        allotment.full_clean()
        allotment.save()
    except Exception as e:
        if hasattr(e, 'message_dict'):
            msg = '; '.join(f'{field}: {errors[0]}' for field, errors in e.message_dict.items())
        else:
            msg = str(e)
        raise Exception(f'Could not save allotment: {msg}')

    return 'Assigned' if created else 'Updated'


def create_or_update_allotment(allocation_id: int, amount: float, quota) -> str:
    allocation = get_object_or_404(Allocation, pk=allocation_id)

    return create_update_allotment(allocation, amount, quota)
