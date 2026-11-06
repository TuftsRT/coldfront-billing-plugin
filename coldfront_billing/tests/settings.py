"""
Django settings for coldfront_billing plugin tests.
Extends coldfront.config.settings and adds coldfront_billing to INSTALLED_APPS
so migrations run and models are available during tests.
"""

from coldfront.config.settings import *  # noqa: F401, F403

INSTALLED_APPS = list(INSTALLED_APPS) + ['coldfront_billing']  # noqa: F405

# In memory, whatever DB_URL says: ColdFront's settings take the database from it, and in a shell
# where it names a real server, the tests would create their database there.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# a deliberately weak hasher: creating users is much faster, and nothing here checks its strength
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
