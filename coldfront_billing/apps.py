from django.apps import AppConfig
from django.conf import settings


class ColdfrontBillingConfig(AppConfig):
    name = 'coldfront_billing'
    verbose_name = 'ColdFront Billing'

    def ready(self):
        context_processor = 'coldfront_billing.context_processor.billing_role'

        templates = settings.TEMPLATES
        options = templates[0].setdefault('OPTIONS', {})
        processors = options.setdefault('context_processors', [])

        if context_processor not in processors:
            processors.append(context_processor)
