from django import forms


class ReportFilterForm(forms.Form):
    username = forms.CharField(max_length=50, required=False, label="Username (utln)")
    project_key = forms.SlugField(max_length=50, required=False, label="Project Key")
    project_title = forms.CharField(max_length=100, required=False, label="Project Title")
    billing_code = forms.CharField(max_length=50, required=False, label="Billing Code")
