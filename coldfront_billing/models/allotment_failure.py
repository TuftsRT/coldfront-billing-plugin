from django.conf import settings
from django.db import models
from django.utils import timezone

from coldfront.core.allocation.models import Allocation


class NoCostQuotaAllotmentFailure(models.Model):
    """
    A requested no-cost quota allotment that could not be applied.

    When an allocation becomes active, or a change to it is approved, the allotment the requester
    asked for is applied (signals._apply_no_cost_quota_allotment_if_requested). A failure there
    must not stop the allocation being provisioned, so it is recorded here instead of raised,
    for someone to apply the allotment by hand or decide not to.

    Unresolved failures are the ones still needing attention. One is resolved when an allotment
    from the same quota is later saved for the allocation (allotments.create_update_allotment),
    or when someone marks it dealt with (resolve()).
    """

    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name="no_cost_quota_allotment_failures",
    )
    no_cost_quota = models.ForeignKey(
        "coldfront_billing.NoCostQuota",
        null=True,
        blank=True,
        # keep the record if the quota goes: it still says what was asked for and why it failed
        on_delete=models.SET_NULL,
        related_name="allotment_failures",
        help_text="The quota the requester asked to apply, if it could be found.",
    )
    requested_value = models.CharField(
        max_length=128,
        blank=True,
        help_text="The request as stored on the allocation: the id of the no-cost quota to apply.",
    )
    message = models.TextField(help_text="Why the allotment could not be applied.")
    created = models.DateTimeField(auto_now_add=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        # keep the record when the account goes away: who resolved it is history
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Who marked it dealt with. Empty if a later allotment resolved it.",
    )
    resolution_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "no-cost quota allotment failure"
        verbose_name_plural = "no-cost quota allotment failures"

    def resolve(self, user=None, note=""):
        """Mark this failure dealt with, by `user`, or by a later allotment if None. A no-op if already resolved."""
        if self.resolved_at is not None:
            return False
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_note = note[: self._meta.get_field("resolution_note").max_length]
        self.save(update_fields=["resolved_at", "resolved_by", "resolution_note"])
        return True

    def __str__(self):
        return f"Allotment failure on allocation {self.allocation_id}"
