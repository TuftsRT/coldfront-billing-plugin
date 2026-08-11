"""
Shared constants and abstract base for quota models (NoCostQuota, NoCostQuotaGroup).
"""

from decimal import Decimal
from django.core.validators import MinValueValidator

from django.core.exceptions import ValidationError
from django.db import models

UNITS_CHOICES = [
    ('TB', 'TB'),
    ('GB', 'GB'),
]

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
    amount = models.FloatField(help_text='Total quota amount') # deprecated, replaced by amount_tb
    amount_tb = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text='Quota amount',
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    ) # 3 decimal places to support GB precision (e.g., 0.001 TB = 1 GB)
    units = models.CharField(
        max_length=16,
        choices=UNITS_CHOICES,
        default='TB',
        help_text='Units for the quota (default: TB). Allowed: TB, GB.',
    ) # affects how amount and minimum_increment are displayed and validated
    minimum_increment = models.FloatField(help_text='Minimum allocation increment') #deprecated, replaced by increment_gb
    increment_gb = models.IntegerField(
        help_text='Allocation increment',
        default=10,
        validators=[MinValueValidator(int(1))]
    ) # e.g. 10GB minimum increment == 0.01TB
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.units not in dict(UNITS_CHOICES):
            raise ValidationError({'units': f'Invalid units: {self.units}. Allowed: {", ".join(dict(UNITS_CHOICES).keys())}.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
