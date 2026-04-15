from typing import ClassVar

from django import forms

from coldfront_billing.models import CostCenter


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
        queryset=CostCenter.objects.all().order_by('name'),
        to_field_name='name',
        label='Cost Center',
        required=False,
        empty_label='Select cost center...',
        widget=forms.Select(attrs={'class': 'form-control custom-select'}),
        help_text='Select the cost center where the project cost will be initially assigned. '
        'To update the value or split the cost between multiple Cost Centers, '
        'visit the "Billing" page under the "Project" menu after the request has been approved.'
        'If you are not sure about the cost center - leave it blank',
    )


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
