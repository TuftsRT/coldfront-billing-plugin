from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from pydantic import ValidationError as PydanticValidationError

from coldfront.core.project.models import Project

from coldfront_billing.schemas import CostCenterSchema

User = get_user_model()


class CostCenter(models.Model):
    name = models.CharField(max_length=60, unique=True, help_text="Unique identifier for the cost center")
    cost_center_type = models.CharField(
        max_length=16,
        choices={"department": "department", "grant": "grant"},
        default="department",
        help_text="Cost center type (department or grant)",
    )

    def __str__(self):
        return self.name


class CostCenterAssignment(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="cost_center_assignment",
        help_text="Project associated with this cost center assignment",
    )
    assignments = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON field storing cost center assignments with percentages",
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cost Center Assignment"
        verbose_name_plural = "Cost Center Assignments"

    def __str__(self):
        return f"Cost Center Assignment for {self.project.title}"

    def clean(self):
        super().clean()

        if not self.assignments:
            return

        try:
            validated = CostCenterSchema.model_validate({"assignments": self.assignments})
        except PydanticValidationError as e:
            raise ValidationError({"assignments": e.errors()})

        # normalization (omit optional keys that are null, e.g. grant)
        self.assignments = validated.model_dump(mode="json", exclude_none=True)["assignments"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
