from typing import ClassVar

from django import forms


class BillingSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'Username'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
