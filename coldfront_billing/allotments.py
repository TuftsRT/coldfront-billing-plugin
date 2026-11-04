from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from coldfront.core.allocation.models import Allocation

from coldfront_billing.constants import QUOTA_ATTR_NAME
from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment


def create_update_allotment(allocation: Allocation, amount: Decimal, quota: NoCostQuota, append: bool = False) -> str:
    # Validate before writing anything, so a rejected amount leaves no allotment behind.
    # The row lock keeps two appends to one allotment from losing an update.
    try:
        with transaction.atomic():
            allotment = (
                NoCostQuotaAllotment.objects.select_for_update()
                .filter(no_cost_quota=quota, allocation=allocation)
                .first()
            )
            created = allotment is None
            if created:
                allotment = NoCostQuotaAllotment(no_cost_quota=quota, allocation=allocation, amount_tb=amount)
            elif append:
                allotment.amount_tb += amount
            else:
                allotment.amount_tb = amount

            allotment.full_clean()
            allotment.save()
    except Exception as e:
        if hasattr(e, 'message_dict'):
            msg = '; '.join(f'{field}: {errors[0]}' for field, errors in e.message_dict.items())
        else:
            msg = str(e)
        raise Exception(f'Could not save allotment: {msg}')

    return 'Assigned' if created else 'Updated'


def create_or_update_allotment(allocation_id: int, amount: Decimal, quota: NoCostQuota) -> str:
    allocation = get_object_or_404(Allocation, pk=allocation_id)

    return create_update_allotment(allocation, amount, quota)


def reduce_allotments_evenly(allotments: list[NoCostQuotaAllotment]) -> list:
    """
    Reduce ``value`` from ``allotments`` as evenly as possible, capping each
    reduction at the allotment's ``amount_tb`` so it never drops below zero.
    Amount an allotment can't absorb is redistributed evenly among the
    remaining allotments (water-filling), so the reduction is spread as evenly
    as their amounts allow rather than exhausting them in order. Any allotment
    that changed is saved. Returns the amount subtracted from each allotment,
    in the same order as ``allotments``.
    """
    parts = [Decimal(0) for _ in allotments]
    # calculate the reduction_value by subtracting the sum of current allotment amounts and subtracting the quota value from the associated Allocation
    quota_value = allotments[0].allocation.get_attribute(QUOTA_ATTR_NAME, typed=False)
    reduction_value = sum(allotment.amount_tb for allotment in allotments) - Decimal(quota_value)
    remaining = reduction_value
    open_indices = [i for i, allotment in enumerate(allotments) if allotment.amount_tb > 0]

    while remaining > 0 and open_indices:
        share = remaining / len(open_indices)
        still_open = []
        for i in open_indices:
            available = allotments[i].amount_tb - parts[i]
            take = min(share, available)
            parts[i] += take
            remaining -= take
            if parts[i] < allotments[i].amount_tb:
                still_open.append(i)
        if len(still_open) == len(open_indices):
            break
        open_indices = still_open

    for allotment, part in zip(allotments, parts):
        if part > 0:
            allotment.amount_tb -= part
            if allotment.amount_tb <= 0:
                # delete empty allotments
                allotment.delete()
            else:
                allotment.save()

    return list(zip(allotments, parts))
