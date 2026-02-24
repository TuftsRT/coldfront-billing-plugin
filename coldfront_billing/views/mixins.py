from django.conf import settings

PAGINATE_BY = getattr(settings, 'COLDFRONT_BILLING_PAGINATE_BY', 25)
