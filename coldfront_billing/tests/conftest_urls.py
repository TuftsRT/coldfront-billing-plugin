"""
URL configuration for tests.
This ensures that billing URLs are available during testing.
"""

from django.urls import include, path

from coldfront.config.urls import urlpatterns as coldfront_urlpatterns

# No fallback if this import fails: without ColdFront's URLs (login and the rest), view tests fail
# later with a misleading NoReverseMatch instead of the real import error.
urlpatterns = coldfront_urlpatterns + [
    path("plugins/", include("coldfront_billing.urls")),
]
