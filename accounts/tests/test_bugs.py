"""
Bugs found before launch, in accounts.

A test tagged `known_bug` FAILS on purpose: it describes the correct
behaviour, and the bug is still in the code. Each fix patch removes the tag
from its own tests, so from then on they run with everything else and stop
the bug from ever coming back.

    python manage.py test --settings=core.settings_test --tag=known_bug          # only the open bugs
    python manage.py test --settings=core.settings_test --exclude-tag=known_bug  # everything else
"""
import importlib
import importlib.util
import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings, tag

from core.factories import make_master

SAFE_SECRET = 'x' * 50


def production_errors(**settings_overrides):
    """Run the production-settings check (bug 11) with some settings changed."""
    from accounts import checks
    base = {'DEBUG': False, 'SECRET_KEY': SAFE_SECRET, 'RESEND_API_KEY': 're_test_key'}
    base.update(settings_overrides)
    with override_settings(**base):
        return [e.id for e in checks.production_settings(None)]


class AccountBugs(TestCase):
    def setUp(self):
        self.lenient = Client(raise_request_exception=False)   # shows a 500 as a response instead of crashing the test

    # ── Bug 6 ────────────────────────────────────────────────────────────
    def test_bug06_login_never_redirects_to_another_site(self):
        """
        login_view does redirect(next) with whatever ?next= says, so
        showpiecehub.com/auth/login/?next=https://evil.example is a
        ready-made phishing link. Correct: ignore off-site `next` values.
        """
        make_master('ana', email='ana@example.com', password='right-pass-1')
        for evil in ('https://evil.example/phish', '//evil.example/phish'):
            with self.subTest(next=evil):
                self.client.logout()
                response = self.client.post('/auth/login/', {
                    'username': 'ana@example.com', 'password': 'right-pass-1', 'next': evil,
                })
                self.assertEqual(response['Location'], '/dashboard/')

    # ── Bug 7 ────────────────────────────────────────────────────────────
    def test_bug07_same_email_with_different_capitals_cannot_register_twice(self):
        """
        register_view checks `email=` (case-sensitive), but login looks users
        up with `email__iexact`. Two accounts can share an email, and login by
        email then picks one of them arbitrarily.
        Correct: the second registration is refused.
        """
        self.client.post('/auth/register/', {'username': 'first', 'email': 'Same@Example.com',
                                             'password': 'secret-123', 'specialty': 'barber'})
        self.client.logout()
        self.client.post('/auth/register/', {'username': 'second', 'email': 'same@example.com',
                                             'password': 'secret-123', 'specialty': 'barber'})
        self.assertEqual(User.objects.filter(email__iexact='same@example.com').count(), 1)

    # ── Bug 11 ───────────────────────────────────────────────────────────
    def test_bug11_production_refuses_to_start_with_unsafe_settings(self):
        """
        If Render is missing SECRET_KEY, DATABASE_URL or RESEND_API_KEY, the
        app quietly falls back to a public key, a throwaway SQLite file, or
        "print emails to the log". Nothing warns you. Correct: a check that
        `manage.py check --deploy` runs and that fails the deploy loudly.
        """
        self.assertIsNotNone(importlib.util.find_spec('accounts.checks'),
                             'accounts/checks.py does not exist yet')
        self.assertEqual(production_errors(), [])                                   # good settings pass
        self.assertIn('showpiece.E001', production_errors(SECRET_KEY='dev-secret-change-this'))
        self.assertIn('showpiece.E001', production_errors(SECRET_KEY='short'))
        sqlite = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}}
        self.assertIn('showpiece.E002', production_errors(DATABASES=sqlite))
        self.assertIn('showpiece.E003', production_errors(RESEND_API_KEY=''))
        with mock.patch.dict(os.environ, {'RENDER': 'true'}):
            self.assertIn('showpiece.E004', production_errors(DEBUG=True))         # debug mode on Render
        self.assertEqual(production_errors(DEBUG=True, SECRET_KEY='dev-secret-change-this'), [])  # your laptop

    # ── Bug 12 ───────────────────────────────────────────────────────────
    def test_bug12_usernames_that_break_pages_are_refused(self):
        """
        Registration accepts any username. "john/doe" breaks every link to
        the master's pages, "edit" collides with /profile/edit/, and a
        200-character name crashes the database insert.
        Correct: only letters, digits and . _ - (max 30), and no reserved names.
        """
        # (the 200-character name stays last: today it breaks the database transaction for whatever follows)
        for i, bad in enumerate(('john/doe', 'john doe', 'edit', 'upload-avatar', '<b>ana</b>', 'x' * 200)):
            with self.subTest(username=bad[:20]):
                self.lenient.logout()
                response = self.lenient.post('/auth/register/', {
                    'username': bad, 'email': f'person{i}@example.com', 'password': 'secret-123',
                    'specialty': 'barber'})
                self.assertNotEqual(response.status_code, 500)
                self.assertFalse(User.objects.filter(username=bad).exists())

    def test_bug12b_email_must_look_like_an_email(self):
        """Booking notifications go to this address, so 'not-an-email' must be refused."""
        self.client.post('/auth/register/', {'username': 'ana', 'email': 'not-an-email',
                                             'password': 'secret-123', 'specialty': 'barber'})
        self.assertFalse(User.objects.filter(username='ana').exists())

    # ── Bug 13 ───────────────────────────────────────────────────────────
    def test_bug13_forgot_password_does_not_crash_when_email_is_down(self):
        """
        If the email service fails, "Forgot password" shows a server error
        page. Correct: the normal page, and the failure written to the log.
        """
        make_master('ana', email='ana@example.com')
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError('smtp down')):
            response = self.lenient.post('/auth/forgot-password/', {'email': 'ana@example.com'})
        self.assertNotEqual(response.status_code, 500)

    def test_bug13b_resend_verification_does_not_crash_when_email_is_down(self):
        master = make_master('ana', email='ana@example.com')
        self.lenient.force_login(master.user)
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError('smtp down')):
            response = self.lenient.get('/auth/resend-verification/')
        self.assertEqual(response.status_code, 302)
