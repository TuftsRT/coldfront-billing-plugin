"""
Shared constants and abstract base for quota models (NoCostQuota, NoCostQuotaGroup).
"""

from django.core.exceptions import ValidationError
from django.db import models

UNITS_CHOICES = [
    ('TB', 'TB'),
    ('GB', 'GB'),
]

ALLOWED_UNITS = {'TB': 0.1, 'GB': 100}


class QuotaBase(models.Model):
    """
    Abstract base model for quota amount fields (amount, units, minimum_increment)
    with shared validation. Subclasses must add their own identifying fields.
    """

    description = models.CharField(
        max_length=128,
        blank=True,
        help_text='Human-readable description of the quota type',
    )
    quota_type = models.CharField(max_length=64, help_text='Storage quota name')
    amount = models.FloatField(help_text='Total quota amount')
    units = models.CharField(
        max_length=16,
        choices=UNITS_CHOICES,
        default='TB',
        help_text='Units for the quota (default: TB). Allowed: TB, GB.',
    )
    minimum_increment = models.FloatField(help_text='Minimum allocation increment')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.units not in ALLOWED_UNITS:
            raise ValidationError({'units': f'Invalid units: {self.units}. Allowed: TB, GB.'})
        required = ALLOWED_UNITS[self.units]
        if self.minimum_increment < required:
            raise ValidationError(
                {'minimum_increment': f'Minimum allocation increment must be ≥ {required} for {self.units}.'}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
