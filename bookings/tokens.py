"""
HMAC-signed tokens for email-based booking actions.

Each token includes the booking's reference_code, the action, and an expiry.
Signed with Django's SECRET_KEY so they can't be forged.

Format: base64(<ref>.<action>.<expires_at_unix>).<signature>
"""

import hmac
import hashlib
import base64
import time
from django.conf import settings


# Default token validity: 30 days (covers up to a month-out booking + grace)
DEFAULT_TOKEN_LIFETIME = 60 * 60 * 24 * 30


def make_action_token(reference_code, action, lifetime=DEFAULT_TOKEN_LIFETIME):
    """Build a signed token for a specific booking action."""
    if action not in ('cancel', 'reschedule'):
        raise ValueError(f'Unknown action: {action}')

    expires_at = int(time.time()) + lifetime
    payload    = f'{reference_code}.{action}.{expires_at}'
    sig        = _sign(payload)
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=') + '.' + sig


def parse_action_token(token):
    """
    Verify and decode a token. Returns dict {ref, action} on success, None on failure.
    """
    try:
        encoded, sig = token.rsplit('.', 1)
    except ValueError:
        return None

    # Pad base64 back to multiple of 4
    padded = encoded + '=' * (-len(encoded) % 4)
    try:
        payload = base64.urlsafe_b64decode(padded.encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None

    expected_sig = _sign(payload)
    if not hmac.compare_digest(sig, expected_sig):
        return None

    try:
        ref, action, expires_at = payload.rsplit('.', 2)
        expires_at = int(expires_at)
    except (ValueError, AttributeError):
        return None

    if time.time() > expires_at:
        return None

    if action not in ('cancel', 'reschedule'):
        return None

    return {'ref': ref, 'action': action}


def _sign(payload):
    """HMAC-SHA256 sign with the Django SECRET_KEY."""
    key = settings.SECRET_KEY.encode()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')