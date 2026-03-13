from django.contrib.auth.models import Group
from django.db.models import CASCADE, OneToOneField

from coldfront_billing.models.common import QuotaBase


class NoCostQuotaGroup(QuotaBase):
    """
    Represents a group of no-cost quota settings. When a user is added to the
    linked Django Group, a NoCostQuota is automatically created for them.
    """

    group = OneToOneField(
        Group,
        on_delete=CASCADE,
        related_name='no_cost_quota_group',
        help_text='Django Group - when a user is added to this group, a NoCostQuota is created for them',
    )

    def __str__(self):
        return self.group.name
