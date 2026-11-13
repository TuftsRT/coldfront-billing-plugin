"""A stand-in for the storage plugin's storage_quota section, which billing's card reads the quota from.

Billing doesn't depend on the storage plugin, so its tests register this instead: the same name, the same
`quota` field (so the field is named storage_quota-quota, billing's default), and, like storage's, it
applies to Storage resources unless their quota_on_request resource attribute is No.
"""

from coldfront_utils.allocation_request import RequestSection, RequestSectionForm
from django import forms


class StandInQuotaForm(RequestSectionForm):
    quota = forms.DecimalField(min_value=0)


class StandInQuotaSection(RequestSection):
    name = "storage_quota"
    order = 10
    form_class = StandInQuotaForm
    template = "test_sections/quota.html"

    def applies(self):
        return (
            self.resource.resource_type.name == "Storage"
            and self.resource.get_attribute("quota_on_request", expand=False, typed=False) != "No"
        )

    def save(self, allocation, form):
        pass
