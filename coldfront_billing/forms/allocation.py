from typing import ClassVar

from django import forms


class AllocationSearchForm(forms.Form):
    PROJECT: ClassVar[str] = "Project name"

    STATUS_ALL = ""
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    STATUS_CHOICES = [
        (STATUS_ALL, "All allocations"),
        (STATUS_ACTIVE, "Only active allocations"),
        (STATUS_INACTIVE, "Only not active allocations"),
    ]

    project = forms.CharField(label=PROJECT, max_length=100, required=False)
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.RadioSelect,
        label="Allocation status",
    )
