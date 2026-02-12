from typing import ClassVar
import json

from django import forms
from coldfront.core.project.models import Project
from .models import CostCenter


class BillingSearchForm(forms.Form):
    LAST_NAME: ClassVar[str] = 'Last Name'
    USERNAME: ClassVar[str] = 'Username'

    last_name = forms.CharField(label=LAST_NAME, max_length=100, required=False)
    username = forms.CharField(label=USERNAME, max_length=100, required=False)


class CostCenterAssignmentForm(forms.Form):
    """Form for handling cost center assignment from modal via JSON."""

    project_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )
    # CharField - because the data comes in as a JSON string
    assignments = forms.CharField(
        widget=forms.HiddenInput()
    )

    def clean_project_id(self) -> int:
        """Validate that the project exists."""
        project_id = self.cleaned_data['project_id']
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise forms.ValidationError("Invalid project ID.")
        return project_id

    def clean_assignments(self) -> dict:
        json_string = self.cleaned_data['assignments']

        try:
            assignments_data = json.loads(json_string)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON data format.")

        if not isinstance(assignments_data, dict):
            raise ValidationError("Assignments must be a dictionary.")

        valid_dept_ids = set(
            CostCenter.objects.values_list('dept_id', flat=True)
        )
        for dept_id, percentage in assignments_data.items():
            if dept_id not in valid_dept_ids:
                raise ValidationError(
                    f"Cost Center '{dept_id}' does not exist.")
            if not isinstance(percentage, int):
                raise ValidationError(
                    f"Percentage for '{dept_id}' must be an integer.")

        return assignments_data
