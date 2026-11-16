"""
Production safety checks.

Render runs these when the Build Command includes:

    python manage.py check --deploy --fail-level ERROR

If one of the settings below is missing in production, the deploy stops with
a clear message, instead of the site quietly running with unsafe defaults.
On your laptop (DEBUG=True, not on Render) nothing is checked.
"""
import os

from django.conf import settings
from django.core.checks import Error, Tags, register

INSECURE_DEFAULT_KEY = 'dev-secret-change-this'


@register(Tags.security, deploy=True)
def production_settings(app_configs, **kwargs):
    on_render = os.environ.get('RENDER') == 'true'   # Render always sets RENDER=true
    if settings.DEBUG and not on_render:
        return []

    errors = []
    if settings.DEBUG:
        errors.append(Error(
            'DEBUG is on in production: visitors would see your code when a page crashes.',
            hint='Set DEBUG=False in Render -> Environment.',
            id='showpiece.E004',
        ))
    if settings.SECRET_KEY == INSECURE_DEFAULT_KEY or len(settings.SECRET_KEY) < 40:
        errors.append(Error(
            'SECRET_KEY is missing or too short: anyone could forge login sessions and email links.',
            hint='Set SECRET_KEY in Render -> Environment to the output of '
                 'python -c "import secrets; print(secrets.token_urlsafe(50))"',
            id='showpiece.E001',
        ))
    if 'sqlite' in settings.DATABASES['default']['ENGINE']:
        errors.append(Error(
            'DATABASE_URL is not set: production would use a throwaway SQLite file that is wiped on every deploy.',
            hint='Set DATABASE_URL in Render -> Environment to your Postgres URL.',
            id='showpiece.E002',
        ))
    if not getattr(settings, 'RESEND_API_KEY', ''):
        errors.append(Error(
            'RESEND_API_KEY is not set: no emails (including booking codes) would be sent.',
            hint='Set RESEND_API_KEY in Render -> Environment.',
            id='showpiece.E003',
        ))
    return errors
