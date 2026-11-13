"""
Django settings for coldfront_billing plugin tests.
Extends coldfront.config.settings and adds coldfront_billing to INSTALLED_APPS
so migrations run and models are available during tests.
"""

from pathlib import Path

from coldfront.config.settings import *  # noqa: F401, F403

# with the request form the billing_cost section adds its card to, as a deployment installs it
INSTALLED_APPS = list(INSTALLED_APPS) + ["coldfront_billing", "coldfront_utils.allocation_request"]  # noqa: F405

# In memory, whatever DB_URL says: ColdFront's settings take the database from it, and in a shell
# where it names a real server, the tests would create their database there.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# a deliberately weak hasher: creating users is much faster, and nothing here checks its strength
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# the card template of the storage quota section's stand-in (tests/quota_section_stand_in.py)
TEMPLATES[0]["DIRS"] = [*TEMPLATES[0]["DIRS"], str(Path(__file__).resolve().parent / "templates")]  # noqa: F405
