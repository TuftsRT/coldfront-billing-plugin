from typing import Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError

from coldfront_billing.models import CostCenter


class AllocationDetailsForm(forms.Form):
    """Form for specifying the storage quota when completing a storage allocation request."""

    quota_in_terabyte = forms.DecimalField(
        label='Storage Quota (TB)',
        required=True,
        min_value=0.1,
        widget=forms.NumberInput(attrs={'step': '0.1', 'min': '0.1', 'class': 'form-control'}),
        help_text='Specify the storage quota in terabytes for your allocation. The minimum allowed value is 0.1 TB.',
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
