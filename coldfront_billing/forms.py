import json
from typing import ClassVar

from coldfront.core.project.models import Project
from django import forms
from django.core.exceptions import ValidationError

from .models import CostCenter


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'PI name'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
    no_cost_center = forms.BooleanField(
        label='Only projects without any cost center assigned',
        required=False,
    )


class CostCenterAssignmentForm(forms.Form):
    """Form for handling cost center assignment from modal via JSON."""

    project_id = forms.IntegerField(widget=forms.HiddenInput())
    # CharField - because the data comes in as a JSON string
    assignments = forms.CharField(widget=forms.HiddenInput())

    def clean_project_id(self) -> int:
        """Validate that the project exists."""
        project_id = self.cleaned_data['project_id']
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise forms.ValidationError('Invalid project ID.')
        return project_id

    def clean_assignments(self) -> dict:
        json_string = self.cleaned_data['assignments']

        try:
            assignments_data = json.loads(json_string)
        except json.JSONDecodeError:
            raise ValidationError('Invalid JSON data format.')

        if not isinstance(assignments_data, dict):
            raise ValidationError('Assignments must be a dictionary.')

        valid_dept_ids = set(CostCenter.objects.values_list('dept_id', flat=True))

        for dept_id, percentage in assignments_data.items():
            if dept_id not in valid_dept_ids:
                raise ValidationError(f"Cost Center '{dept_id}' does not exist.")
            if not isinstance(percentage, int):
                raise ValidationError(f"Percentage for '{dept_id}' must be an integer.")

        return assignments_data
