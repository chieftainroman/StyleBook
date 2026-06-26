from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Subclass of Django's password reset token generator, repurposed for email verification.
    Token hash includes user.pk + timestamp + email_verified state, so used tokens become invalid.
    """
    def _make_hash_value(self, user, timestamp):
        verified = user.profile.email_verified if hasattr(user, 'profile') else False
        return f'{user.pk}{timestamp}{verified}{user.email}'


email_verification_token = EmailVerificationTokenGenerator()


def make_user_token_url(user, token_generator, base_path):
    """
    Build a verification or reset URL like:
    /auth/verify-email/MQ/cd0-abc.../  
    where MQ is base64-encoded user.pk and cd0-abc is the token.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    return f'{base_path}{uid}/{token}/'


def decode_uid(uidb64):
    """Decode a base64 user pk back to an integer. Returns None on failure."""
    try:
        return int(urlsafe_base64_decode(uidb64).decode())
    except (TypeError, ValueError, OverflowError):
        return None