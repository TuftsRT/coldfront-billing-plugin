from django import forms

class BillingSearchForm(forms.Form):

    LAST_NAME = "Last Name"
    USERNAME = "Username"

    last_name = forms.CharField(label=LAST_NAME, max_length=100, required=False)
    username = forms.CharField(label=USERNAME, max_length=100, required=False)
