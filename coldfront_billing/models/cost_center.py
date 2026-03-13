from coldfront.core.project.models import Project
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from coldfront_billing.schemas import CostCenterSchema

User = get_user_model()


class CostCenter(models.Model):
    dept_id = models.CharField(max_length=60, unique=True, help_text='Unique identifier for the cost center')

    def __str__(self):
        return self.dept_id


class CostCenterAssignment(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='cost_center_assignment',
        help_text='Project associated with this cost center assignment',
    )
    assignments = models.JSONField(blank=True, help_text='JSON field storing cost center assignments with percentages')
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cost Center Assignment'
        verbose_name_plural = 'Cost Center Assignments'

    def __str__(self):
        return f'Cost Center Assignment for {self.project.title}'

    def clean(self):
        """Validate the JSON field using Pydantic schema."""
        if self.assignments:
            try:
                CostCenterSchema(assignments=self.assignments)
            except Exception as e:
                raise ValidationError(f'Invalid cost center assignments: {e}')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
