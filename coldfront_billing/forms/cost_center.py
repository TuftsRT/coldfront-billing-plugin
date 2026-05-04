import json
from typing import Any, List

from coldfront.core.project.models import Project
from django import forms
from django.core.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from coldfront_billing.models import CostCenter
from coldfront_billing.schemas import CostCenterSchema


class CostCenterAssignmentForm(forms.Form):
    """Form for handling cost center assignment from modal via JSON."""

    project_id = forms.IntegerField(widget=forms.HiddenInput())
    # CharField - because the data comes in as a JSON string
    assignments = forms.CharField(widget=forms.HiddenInput())

    def clean_project_id(self) -> int:
        """Validate that the project exists."""
        project_id = self.cleaned_data['project_id']
        if not Project.objects.filter(id=project_id).exists():
            raise forms.ValidationError('Invalid project ID.')
        return project_id

    def clean_assignments(self) -> List[dict[str, Any]]:
        json_string = self.cleaned_data['assignments']

        try:
            assignments_data = json.loads(json_string)
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid JSON data format.')

        if not isinstance(assignments_data, list):
            raise forms.ValidationError('Assignments must be a list.')

        if not assignments_data:
            raise forms.ValidationError('At least one assignment is required.')

        assignements: list[dict[str, Any]] = []

        for i, row in enumerate(assignments_data):
            if not isinstance(row, dict):
                raise forms.ValidationError(f'Assignment {i} must be a JSON object.')

            dept = row.get('department')
            grant = row.get('grant')
            pct = row.get('percentage')

            if not isinstance(dept, str) or not dept.strip():
                raise forms.ValidationError(f'Assignment {i} must include a non-empty department string.')

            if type(pct) is not int:
                raise forms.ValidationError(f'Percentage for {dept!r} must be an integer.')

            assignements.append({'department': dept, 'percentage': pct, **({'grant': grant} if grant else {})})

        for cost_center in ('department', 'grant'):
            values_set = {item.get(cost_center) for item in assignements if item.get(cost_center) is not None}

            valid_values = set(
                CostCenter.objects.filter(name__in=values_set, cost_center_type=cost_center).values_list(
                    'name', flat=True
                )
            )

            if invalid := values_set - valid_values:
                invalid_list = ', '.join(sorted(invalid))
                raise forms.ValidationError(f'Unknown {cost_center}(s): {invalid_list}.')

        try:
            validated = CostCenterSchema.model_validate({'assignments': assignements})
        except PydanticValidationError as e:
            first = e.errors()[0] if e.errors() else None
            msg = first.get('msg', 'Invalid assignments.') if first else 'Invalid assignments.'
            raise ValidationError(msg)

        return [a.model_dump(mode='json', exclude_none=True) for a in validated.assignments]
