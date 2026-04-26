from django.db import models


class BillingScheduleHistory(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED_AUTOASSIGN = 'FAILED_AUTOASSIGN', 'Failed autoassign'
        FAILED_REPORT = 'FAILED_REPORT', 'Failed report'
        FAILED_MAIL = 'FAILED_MAIL', 'Failed mail'

    started = models.DateTimeField()
    stopped = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=64, choices=Status.choices)
    details = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Billing schedule history'
        verbose_name_plural = 'Billing schedule histories'
