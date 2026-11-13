from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from coldfront.core.allocation.models import Allocation, AllocationAttribute, AllocationAttributeType

from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME, NO_COST_QUOTA_TYPE_ATTR_NAME, QUOTA_ATTR_NAME
from coldfront_billing.models import (
    NoCostQuota,
    NoCostQuotaAllotment,
    NoCostQuotaAllotmentFailure,
    quota_with_remaining,
)


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

            # however it was applied -- by hand, auto-assigned or a later request -- an allotment
            # from this quota answers any earlier failure to apply one
            NoCostQuotaAllotmentFailure.objects.filter(
                allocation=allocation, no_cost_quota=quota, resolved_at__isnull=True
            ).update(resolved_at=timezone.now(), resolution_note="Resolved by a later allotment.")
    except Exception as e:
        if hasattr(e, "message_dict"):
            msg = "; ".join(f"{field}: {errors[0]}" for field, errors in e.message_dict.items())
        else:
            msg = str(e)
        raise Exception(f"Could not save allotment: {msg}")

    return "Assigned" if created else "Updated"


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


def no_cost_quota_with_remaining(resource, project, user):
    """The no-cost quota a request for `resource` by `user` would draw on, if it has something left, or None: the
    user's quota of the resource's no-cost quota type, or the PI's when the user is a superuser. Doesn't check
    that the user may apply it (prefetch.can_apply_no_cost_quota)."""
    quota_type = resource.get_attribute(NO_COST_QUOTA_TYPE_ATTR_NAME, expand=False, typed=False)
    if not quota_type:
        return None
    quota_user = project.pi if user.is_superuser else user
    quota = quota_with_remaining.filter(user=quota_user, quota_type=quota_type).first()
    return quota if quota is not None and quota.remaining_normalized > 0 else None


def record_no_cost_quota_request(allocation: Allocation, quota_pk) -> bool:
    """Record that `allocation` should have no-cost quota `quota_pk` applied when it's activated or its change is
    approved (signals._apply_no_cost_quota_allotment_if_requested reads it). Returns False, recording nothing,
    if the attribute type is missing (migration 0009 creates it)."""
    attribute_type = AllocationAttributeType.objects.filter(name=ALLOCATION_QUOTA_ATTRIBUTE_NAME).first()
    if attribute_type is None:
        return False
    AllocationAttribute.objects.update_or_create(
        allocation=allocation, allocation_attribute_type=attribute_type, defaults={"value": str(quota_pk)}
    )
    return True
