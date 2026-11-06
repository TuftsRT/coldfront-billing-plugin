from typing import ClassVar

from django import forms


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = "PI name"
    TITLE: ClassVar[str] = "Project title"
    COST_CENTER: ClassVar[str] = "Cost center"

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
    project_title = forms.CharField(label=TITLE, max_length=100, required=False)
    cost_center = forms.CharField(
        label=COST_CENTER,
        max_length=100,
        required=False,
        help_text="Matches any part of assigned department or grant names (case-insensitive).",
    )
    no_cost_center = forms.BooleanField(
        label="Only projects without any cost center assigned",
        required=False,
    )
