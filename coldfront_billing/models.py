from typing import List
from django.db import models
from django.core.exceptions import ValidationError
from coldfront.core.project.models import Project
import json


class CostCenter(models.Model):
    dept_id = models.CharField(max_length=60, unique=True, help_text="Unique identifier for the cost center")


class CostCenterAssignment(models.Model):
    """Model to store cost center assignments for projects using JSON field."""

    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='cost_center_assignment',
        help_text="Project associated with this cost center assignment"
    )

    assignments = models.JSONField(
        help_text="JSON field storing cost center assignments with percentages"
    )

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cost Center Assignment"
        verbose_name_plural = "Cost Center Assignments"

    def __str__(self):
        return f"Cost Center Assignment for {self.project.title}"

    # def clean(self):
    #     """Validate the JSON field using Pydantic schema."""
    #     if self.assignments:
    #         try:
    #             # Validate using Pydantic
    #             CostCenterSchema(assignments=self.assignments)
    #         except Exception as e:
    #             raise ValidationError(f'Invalid cost center assignments: {e}')
    #
    # def save(self, *args, **kwargs):
    #     """Override save to ensure validation."""
    #     self.full_clean()
    #     super().save(*args, **kwargs)

    def get_cost_centers_display(self):
        """Return a formatted string of cost centers for display purposes."""
        if not self.assignments:
            return '-'
        return self.assignments
    #
    #     try:
    #         validated = CostCenterSchema(assignments=self.assignments)
    #         return ', '.join([
    #             f"{item.cost_center} ({item.percentage}%)"
    #             for item in validated.assignments
    #         ])
    #     except Exception:
    #         return 'Invalid data'
    #
    # @classmethod
    # def create_from_dict(cls, project, assignments_list):
    #     """Create a CostCenterAssignment from a list of dictionaries."""
    #     schema = CostCenterSchema(assignments=assignments_list)
    #     return cls.objects.create(
    #         project=project,
    #         assignments=schema.model_dump()['assignments']

