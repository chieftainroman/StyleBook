"""
Settings used ONLY when running the test suite:

    python manage.py test --settings=core.settings_test

Why a separate file:
  * It ignores DATABASE_URL on purpose. Your .env may point DATABASE_URL at
    the production database on Render, and a test run must never touch it.
    Tests use TEST_DATABASE_URL instead (default: a local Postgres). Django
    then creates and destroys its own throwaway "test_<name>" database there.
  * Postgres is required, not SQLite, because MasterProfile.languages is an
    ArrayField.
  * WhiteNoise's manifest storage needs `collectstatic` to have been run;
    tests use plain static storage so templates render without it.
"""
import os

import dj_database_url

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('TEST_DATABASE_URL', 'postgres://postgres@localhost:5432/stylebook'),
    ),
}

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Fast hashing — real password hashing makes every login in a test slow.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Never send real emails from tests (Django also forces this, but be explicit).
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Keep generated links deterministic in assertions.
SITE_URL = 'https://showpiecehub.test'
