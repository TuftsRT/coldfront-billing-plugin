from decimal import Decimal

from coldfront.core.allocation.models import Allocation
from coldfront.core.allocation.signals import allocation_change_approved
from coldfront.core.project.models import Project
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from coldfront_billing.allotments import create_update_allotment
from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME, QUOTA_ATTR_NAME
from coldfront_billing.enums import AllocationStatus, ProjectStatus
from coldfront_billing.models import BillingScheduleSettings, NoCostQuota, NoCostQuotaAllotment, NoCostQuotaGroup
from coldfront_billing.notifications import send_allocation_notification
from coldfront_billing.scheduling import sync_billing_schedule
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining

User = get_user_model()


def _apply_no_cost_quota_allotment_if_requested(allocation: Allocation) -> None:
    """Create/update no-cost allotment when ``ALLOCATION_QUOTA_ATTRIBUTE_NAME`` is set; then remove that attribute."""
    apply_quota_attr = allocation.allocationattribute_set.filter(
        allocation_attribute_type__name=ALLOCATION_QUOTA_ATTRIBUTE_NAME,
    ).first()
    if not apply_quota_attr:
        return

    try:
        quota_pk = int(apply_quota_attr.value)
    except (TypeError, ValueError):
        return

    try:
        no_cost_quota = quota_with_remaining.get(pk=quota_pk)
    except NoCostQuota.DoesNotExist:
        return

    allocation_quota_tb = allocation.get_attribute(QUOTA_ATTR_NAME, typed=True)
    if allocation_quota_tb is None:
        return

    allocation_tb = Decimal(allocation_quota_tb)
    remaining_tb = no_cost_quota.remaining_normalized

    amount = min(allocation_tb, remaining_tb)
    create_update_allotment(allocation, amount, no_cost_quota, append=True)
    apply_quota_attr.delete()


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
        _apply_no_cost_quota_allotment_if_requested(instance)
        send_allocation_notification(instance)


@receiver(allocation_change_approved, dispatch_uid='allocation_change_request_approved_ncq')
def allocation_change_request_approved(sender, allocation_pk, **kwargs):
    """After staff approve an allocation change request, apply no-cost quota allotment if user requested it."""
    allocation = Allocation.objects.get(pk=allocation_pk)
    _apply_no_cost_quota_allotment_if_requested(allocation)
    send_allocation_notification(
        allocation,
        allocation_change_pk=kwargs.get('allocation_change_pk'),
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
