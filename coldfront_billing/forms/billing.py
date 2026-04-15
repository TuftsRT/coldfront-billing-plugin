from typing import ClassVar

from django import forms


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'PI name'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
    no_cost_center = forms.BooleanField(
        label='Only projects without any cost center assigned',
        required=False,
    )
