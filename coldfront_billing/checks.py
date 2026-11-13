"""System checks for the billing plugin."""

from django.apps import apps
from django.core import checks


@checks.register()
def check_allocation_request_app(app_configs, **kwargs):
    """E001: the billing_cost request section is registered, but coldfront_utils.allocation_request isn't
    installed, so no request page would ask for the cost center or offer the no-cost quota."""
    if apps.is_installed("coldfront_utils.allocation_request"):
        return []
    return [
        checks.Error(
            "The billing plugin asks for a paid request's cost center on the allocation request form, but "
            "coldfront_utils.allocation_request isn't installed.",
            hint='Add "coldfront_utils.allocation_request" to INSTALLED_APPS.',
            id="coldfront_billing.E001",
        )
    ]
