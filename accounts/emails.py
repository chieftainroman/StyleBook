from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .tokens import email_verification_token, make_user_token_url


def send_verification_email(request, user):
    """Send a 'verify your email' email with a unique link."""
    path = make_user_token_url(user, email_verification_token, '/auth/verify-email/')
    verify_url = request.build_absolute_uri(path)

    context = {
        'user':       user,
        'verify_url': verify_url,
        'site_name':  'StyleBook',
    }

    subject = 'Verify your email address — StyleBook'
    text_body = render_to_string('emails/verify_email.txt', context)
    html_body = render_to_string('emails/verify_email.html', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


def send_password_reset_email(request, user):
    """Send a password reset email with a unique link."""
    from django.contrib.auth.tokens import default_token_generator
    path = make_user_token_url(user, default_token_generator, '/auth/reset-password/')
    reset_url = request.build_absolute_uri(path)

    context = {
        'user':      user,
        'reset_url': reset_url,
        'site_name': 'StyleBook',
    }

    subject = 'Reset your password — StyleBook'
    text_body = render_to_string('emails/reset_password.txt', context)
    html_body = render_to_string('emails/reset_password.html', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)