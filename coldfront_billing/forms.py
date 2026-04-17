import json
from typing import Any, ClassVar, List

from coldfront.core.project.models import Project
from django import forms
from django.core.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from coldfront_billing.schemas import CostCenterSchema

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
        queryset=CostCenter.objects.filter(cost_center_type='department').order_by('name'),
        to_field_name='name',
        label='Cost Center',
        required=False,
        widget=forms.HiddenInput(),
        help_text='Select the cost center where the project cost will be initially assigned. '
        'To update the value or split the cost between multiple Cost Centers, '
        'visit the "Billing" page under the "Project" menu after the request has been approved.'
        'If you are not sure about the cost center - leave it blank',
    )
    grant = forms.ModelChoiceField(
        queryset=CostCenter.objects.filter(cost_center_type='grant').order_by('name'),
        to_field_name='name',
        label='Grant',
        required=False,
        widget=forms.HiddenInput(),
        help_text='Select the grant where the project cost will be initially assigned. '
        'A cost center must be selected first.',
    )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        cost_center = cleaned_data.get('cost_center')
        grant = cleaned_data.get('grant')
        if grant and cost_center is None:
            self.add_error(
                'grant',
                ValidationError('Select a cost center before choosing a grant.'),
            )
        return cleaned_data


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'PI name'
    TITLE: ClassVar[str] = 'Project title'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
    project_title = forms.CharField(label=TITLE, max_length=100, required=False)
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
