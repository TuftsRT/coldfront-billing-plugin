from django.db import models

from coldfront_billing.constants import BILLING_USE_TEST_SCHEDULING


class BillingScheduleSettings(models.Model):
    SCHEDULE_MONTHLY = 'monthly'
    SCHEDULE_EVERY_5_MINUTES = 'every_5_minutes'

    _SCHEDULE_TYPE_LABELS = {
        SCHEDULE_MONTHLY: 'Monthly',
        SCHEDULE_EVERY_5_MINUTES: 'Every 5 minutes',
    }

    scheduling_enabled = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    notification_email = models.CharField(
        max_length=2048,
        blank=True,
        default='',
        help_text='One or more addresses separated by semicolon or comma.',
    )
    email_subject = models.CharField(
        'Email subject',
        max_length=255,
        blank=True,
        default='',
    )
    email_content = models.TextField(
        'Email content',
        blank=True,
        default='',
    )
    autoassign_no_cost_quota = models.BooleanField(
        'Autoassign no cost quota',
        default=False,
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # optional, useful later when syncing with django-q
    scheduler_external_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Optional external scheduler identifier.',
    )

    class Meta:
        verbose_name = 'Billing schedule settings'
        verbose_name_plural = 'Billing schedule settings'

    def __str__(self):
        return 'Billing schedule settings'

    def get_schedule(self):
        if BILLING_USE_TEST_SCHEDULING:
            return self.SCHEDULE_EVERY_5_MINUTES
        return self.SCHEDULE_MONTHLY

    @property
    def schedule_type_display(self):
        return self._SCHEDULE_TYPE_LABELS[self.get_schedule()]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})
