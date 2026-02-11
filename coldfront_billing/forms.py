from typing import ClassVar

from django import forms
from coldfront.core.project.models import Project
from .models import CostCenter


class BillingSearchForm(forms.Form):
    LAST_NAME: ClassVar[str] = 'Last Name'
    USERNAME: ClassVar[str] = 'Username'

    last_name = forms.CharField(label=LAST_NAME, max_length=100, required=False)
    username = forms.CharField(label=USERNAME, max_length=100, required=False)


class CostCenterAssignmentForm(forms.Form):
    """Form for handling cost center assignment from modal."""

    project_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )

    dept_id = forms.ModelChoiceField(
        queryset=CostCenter.objects.all(),
        to_field_name='dept_id',
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    percentage = forms.IntegerField(
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100'
        })
    )

    def clean_project_id(self):
        """Validate that the project exists."""
        project_id = self.cleaned_data['project_id']
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise forms.ValidationError("Invalid project ID.")
        return project_id

