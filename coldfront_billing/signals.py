from coldfront.core.project.models import Project
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, pre_save
from django.dispatch import receiver

from coldfront_billing.enum import ProjectStatus
from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment, NoCostQuotaGroup

User = get_user_model()


@receiver(m2m_changed, sender=User.groups.through)
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
                'amount': group.amount,
                'units': group.units,
                'minimum_increment': group.minimum_increment,
            },
        )


@receiver(pre_save, sender=Project)
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
