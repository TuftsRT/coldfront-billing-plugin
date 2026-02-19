"""
Django settings for coldfront_billing plugin tests.
Extends coldfront.config.settings and adds coldfront_billing to INSTALLED_APPS
so migrations run and models are available during tests.
"""

from coldfront.config.settings import *  # noqa: F401, F403

INSTALLED_APPS = list(INSTALLED_APPS) + ['coldfront_billing']  # noqa: F405
