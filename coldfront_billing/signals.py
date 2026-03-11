from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from coldfront_billing.models import NoCostQuota, NoCostQuotaGroup

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
