import json
from typing import ClassVar

from coldfront.core.project.models import Project
from django import forms
from django.core.exceptions import ValidationError

from .models import CostCenter


class AllocationDetailsForm(forms.Form):
    """Form for specifying storage quota when completing a storage allocation request."""

    quota_in_terabyte = forms.FloatField(
        label='Storage Quota (TB)',
        required=True,
        min_value=0,
        widget=forms.NumberInput(attrs={'step': '1.0', 'min': '0', 'class': 'form-control'}),
        help_text='Specify the storage quota in terabytes for your allocation.',
    )
    cost_center = forms.ModelChoiceField(
        queryset=CostCenter.objects.all().order_by('dept_id'),
        to_field_name='dept_id',
        label='Cost Center',
        required=False,
        empty_label='Select cost center...',
        widget=forms.Select(attrs={'class': 'form-control custom-select'}),
        help_text='Select the cost center where the project cost will be initially assigned. '
        'To update the value or split the cost between multiple Cost Centers, '
        'visit the "Billing" page under the "Project" menu after the request has been approved.'
        'If you are not sure about the cost center - leave it blank',
    )


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'PI name'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
    no_cost_center = forms.BooleanField(
        label='Only projects without any cost center assigned',
        required=False,
    )


class NoCostQuotaSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'Owner name'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)


class AllocationSearchForm(forms.Form):
    PROJECT: ClassVar[str] = 'Project name'

    STATUS_ALL = ''
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'

    STATUS_CHOICES = [
        (STATUS_ALL, 'All allocations'),
        (STATUS_ACTIVE, 'Only active allocations'),
        (STATUS_INACTIVE, 'Only not active allocations'),
    ]

    project = forms.CharField(label=PROJECT, max_length=100, required=False)
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.RadioSelect,
        label='Allocation status',
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
