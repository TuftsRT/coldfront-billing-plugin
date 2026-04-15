from typing import ClassVar

from django import forms


class NoCostQuotaSearchForm(forms.Form):
    USERNAME: ClassVar[str] = 'Owner name'

    username = forms.CharField(label=USERNAME, max_length=100, required=False)
