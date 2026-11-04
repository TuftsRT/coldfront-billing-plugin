import logging
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from coldfront.core.allocation.models import Allocation
from coldfront.core.allocation.signals import allocation_change_approved
from coldfront.core.project.models import Project

from coldfront_billing.allotments import create_update_allotment
from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME, QUOTA_ATTR_NAME
from coldfront_billing.enums import AllocationStatus, ProjectStatus
from coldfront_billing.models import (
    BillingScheduleSettings,
    NoCostQuota,
    NoCostQuotaAllotment,
    NoCostQuotaAllotmentFailure,
    NoCostQuotaGroup,
)
from coldfront_billing.models.no_cost_quota import quota_with_remaining
from coldfront_billing.notifications import send_allocation_notification
from coldfront_billing.scheduling import sync_billing_schedule

logger = logging.getLogger(__name__)

User = get_user_model()


class AllotmentRequestError(Exception):
    """A requested no-cost allotment can't be applied, for a reason worth telling a person."""


def _apply_no_cost_quota_allotment_if_requested(allocation: Allocation) -> bool:
    """
    Create/update the no-cost allotment requested through ``ALLOCATION_QUOTA_ATTRIBUTE_NAME``,
    then remove that request.

    Never raises: this runs while the allocation is being activated or its change approved, and a
    billing problem must not stop that. A request that can't be applied is logged and recorded as
    a NoCostQuotaAllotmentFailure for someone to deal with, and removed all the same, so a later
    approval doesn't apply it on top of whatever they decide.

    Returns True if a requested allotment was left unapplied, False otherwise (including when
    nothing was requested).
    """
    apply_quota_attr = allocation.allocationattribute_set.filter(
        allocation_attribute_type__name=ALLOCATION_QUOTA_ATTRIBUTE_NAME,
    ).first()
    if not apply_quota_attr:
        return False

    requested_value = apply_quota_attr.value
    no_cost_quota = None
    try:
        # a savepoint, so a database error in here leaves any surrounding transaction usable
        with transaction.atomic():
            no_cost_quota = _requested_quota(requested_value)
            amount = _requested_amount(allocation, no_cost_quota)
            create_update_allotment(allocation, amount, no_cost_quota, append=True)
            apply_quota_attr.delete()
        return False
    except AllotmentRequestError as e:
        message = str(e)
        logger.warning(f'No-cost quota allotment not applied to allocation {allocation.pk}: {message}')
    except Exception as e:
        # create_update_allotment raises a bare Exception with a readable message; name anything else
        message = str(e) if type(e) is Exception else f'{type(e).__name__}: {e}'
        logger.exception(f'No-cost quota allotment not applied to allocation {allocation.pk}')

    try:
        with transaction.atomic():
            NoCostQuotaAllotmentFailure.objects.create(
                allocation=allocation,
                no_cost_quota=no_cost_quota,
                requested_value=requested_value,
                message=message,
            )
            apply_quota_attr.delete()
    except Exception:
        # keep the request, so the failure is at least not lost, and say so in the log
        logger.exception(f'Could not record the failed no-cost quota allotment on allocation {allocation.pk}')
    return True


def _requested_quota(requested_value: str) -> NoCostQuota:
    try:
        quota_pk = int(requested_value)
    except (TypeError, ValueError):
        raise AllotmentRequestError(f'The requested no-cost quota {requested_value!r} is not a quota id.') from None
    try:
        return quota_with_remaining.get(pk=quota_pk)
    except NoCostQuota.DoesNotExist:
        raise AllotmentRequestError(f'The requested no-cost quota {quota_pk} no longer exists.') from None


def _requested_amount(allocation: Allocation, no_cost_quota: NoCostQuota) -> Decimal:
    """As much of the allocation as the quota has left, in TB."""
    # Untyped: the typed value is a float, and Decimal(0.1) is 0.1000000000000000055..., which
    # fails the allotment's max_digits and increment-multiple validation.
    allocation_quota_tb = allocation.get_attribute(QUOTA_ATTR_NAME, typed=False)
    try:
        allocation_tb = Decimal((allocation_quota_tb or '').strip())
    except InvalidOperation:
        raise AllotmentRequestError(
            f'The allocation has no usable {QUOTA_ATTR_NAME} value ({allocation_quota_tb!r}).'
        ) from None

    remaining_tb = no_cost_quota.remaining_normalized
    if remaining_tb <= 0:
        raise AllotmentRequestError(
            f'No-cost quota {no_cost_quota.pk} ({no_cost_quota.user.username}, {no_cost_quota.quota_type}) '
            'has nothing left to allot.'
        )
    return min(allocation_tb, remaining_tb)


@receiver(m2m_changed, sender=User.groups.through, dispatch_uid='user_groups_changed_ncq')
def user_groups_changed(sender, instance: User, action, reverse, model, pk_set, **kwargs):
    """
    When a user is added to the no-cost-quota group, create a NoCostQuota for them
    for each tier type defined in NoCostQuotaGroup.
    """
    if action != 'post_add' or reverse:
        return

    matching_groups = NoCostQuotaGroup.objects.filter(group_id__in=pk_set)
    if not matching_groups.exists():
        return

    for group in matching_groups:
        NoCostQuota.objects.get_or_create(
            user=instance,
            quota_type=group.quota_type,
            defaults={
                'description': group.description or group.group.name,
                'amount_tb': group.amount_tb,
                'units': group.units,
                'increment_gb': group.increment_gb,
            },
        )


@receiver(pre_save, sender=Allocation, dispatch_uid='allocation_became_active_ncq')
def allocation_became_active(sender, instance: Allocation, **kwargs):
    if not instance.pk:
        return
    try:
        old_allocation = Allocation.objects.select_related('status').get(pk=instance.pk)
    except Allocation.DoesNotExist:
        return

    if old_allocation.status.name != AllocationStatus.ACTIVE and instance.status.name == AllocationStatus.ACTIVE:
        pending = _apply_no_cost_quota_allotment_if_requested(instance)
        send_allocation_notification(instance, no_cost_quota_pending=pending)


@receiver(allocation_change_approved, dispatch_uid='allocation_change_request_approved_ncq')
def allocation_change_request_approved(sender, allocation_pk, **kwargs):
    """After staff approve an allocation change request, apply no-cost quota allotment if user requested it."""
    allocation = Allocation.objects.get(pk=allocation_pk)
    pending = _apply_no_cost_quota_allotment_if_requested(allocation)
    send_allocation_notification(
        allocation,
        allocation_change_pk=kwargs.get('allocation_change_pk'),
        no_cost_quota_pending=pending,
    )


@receiver(pre_save, sender=Project, dispatch_uid='project_archived_ncq')
def project_archived(sender, instance: Project, **kwargs):
    # New object, nothing to compare yet
    if not instance.pk:
        return
    try:
        old_project = Project.objects.select_related('status').get(pk=instance.pk)
    except Project.DoesNotExist:
        return

    # Handle only transition from Active to Archived
    if old_project.status.name != ProjectStatus.ARCHIVED and instance.status.name == ProjectStatus.ARCHIVED:
        NoCostQuotaAllotment.objects.filter(allocation__project=instance).delete()


@receiver(post_save, sender=BillingScheduleSettings, dispatch_uid='billing_settings_saved_ncq')
def billing_settings_saved(sender, instance, **kwargs):
    sync_billing_schedule(instance)


@receiver(post_delete, sender=BillingScheduleSettings, dispatch_uid='billing_settings_deleted_ncq')
def billing_settings_deleted(sender, instance, **kwargs):
    sync_billing_schedule(None)
