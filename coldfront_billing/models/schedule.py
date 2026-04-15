from django.db import models


class BillingScheduleSettings(models.Model):
    SCHEDULE_WEEKLY = 'weekly'
    SCHEDULE_MONTHLY = 'monthly'
    SCHEDULE_QUARTERLY = 'quarterly'

    SCHEDULE_TYPE_CHOICES = [
        (SCHEDULE_WEEKLY, 'Weekly'),
        (SCHEDULE_MONTHLY, 'Monthly'),
        (SCHEDULE_QUARTERLY, 'Quarterly'),
    ]

    scheduling_enabled = models.BooleanField(default=True)
    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPE_CHOICES,
        default=SCHEDULE_MONTHLY,
    )
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

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})

    @property
    def next_run_display(self):
        """
        Placeholder for now.
        """
        if not self.scheduling_enabled:
            return 'Disabled'
        return 'Not scheduled yet'
