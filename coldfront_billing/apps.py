from django.apps import AppConfig
from django.conf import settings


class ColdfrontBillingConfig(AppConfig):
    name = 'coldfront_billing'
    verbose_name = 'ColdFront Billing'

    def ready(self):
        import coldfront_billing.signals  # noqa: F401 - register signal handlers

        context_processor = 'coldfront_billing.context_processor.billing_role'

        templates = settings.TEMPLATES
        options = templates[0].setdefault('OPTIONS', {})
        processors = options.setdefault('context_processors', [])

        if context_processor not in processors:
            processors.append(context_processor)

        # Override allocation create view so users specify quota when requesting storage
        import coldfront.core.allocation.views as allocation_views

        from coldfront_billing.views.allocation import AllocationCreateView

        allocation_views.AllocationCreateView = AllocationCreateView
