from django.apps import AppConfig
from django.conf import settings


class ColdfrontBillingConfig(AppConfig):
    name = "coldfront_billing"
    verbose_name = "ColdFront Billing"

    def ready(self):
        import coldfront_billing.signals  # noqa: F401 - register signal handlers

        context_processor = "coldfront_billing.context_processor.billing_role"

        templates = settings.TEMPLATES
        options = templates[0].setdefault("OPTIONS", {})
        processors = options.setdefault("context_processors", [])

        if context_processor not in processors:
            processors.append(context_processor)

        # A paid request's cost center and no-cost quota are asked for on ColdFront's own request form, as a
        # section of coldfront_utils.allocation_request, which must be installed too (check E001)
        from coldfront_utils.allocation_request import register_request_section

        from coldfront_billing import checks  # noqa: F401 -- registers them
        from coldfront_billing.request_section import BillingCostSection

        register_request_section(BillingCostSection)

        # Change requests: ColdFront's view, plus applying a no-cost quota
        import coldfront.core.allocation.views as allocation_views

        from coldfront_billing.views.allocation import BillingAllocationChangeView

        allocation_views.AllocationChangeView = BillingAllocationChangeView
