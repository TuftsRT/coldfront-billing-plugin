"""
URL configuration for tests.
This ensures that billing URLs are available during testing.
"""

from django.urls import include, path

# Try to import coldfront URLs, fallback to just billing URLs
try:
    from coldfront.config.urls import urlpatterns as coldfront_urlpatterns

    urlpatterns = coldfront_urlpatterns + [
        path('plugins/', include('coldfront_billing.urls')),
    ]
except ImportError:
    # Fallback if coldfront URLs can't be imported
    urlpatterns = [
        path('plugins/', include('coldfront_billing.urls')),
    ]
