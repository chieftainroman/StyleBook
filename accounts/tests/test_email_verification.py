"""Tests for email verification links and "resend verification"."""
import re

from django.core import mail
from django.test import TestCase

from accounts.tokens import decode_uid, email_verification_token, make_user_token_url
from core.factories import make_master


class VerifyEmailTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com')
        self.url = make_user_token_url(self.master.user, email_verification_token, '/auth/verify-email/')

    def result(self, url):
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'accounts/verify_result.html')
        return response.context['success']

    def test_valid_link_marks_the_email_verified(self):
        self.assertTrue(self.result(self.url))
        self.master.refresh_from_db()
        self.assertTrue(self.master.email_verified)

    def test_link_only_works_once(self):
        self.result(self.url)
        self.assertFalse(self.result(self.url))

    def test_link_stops_working_if_the_email_changes(self):
        self.master.user.email = 'new@example.com'
        self.master.user.save()
        self.assertFalse(self.result(self.url))

    def test_broken_links_fail_safely(self):
        for url in ('/auth/verify-email/!!!/abc/', '/auth/verify-email/OTk5OTk/abc/', self.url[:-4] + 'xyz/'):
            with self.subTest(url=url):
                self.assertFalse(self.result(url))
        self.master.refresh_from_db()
        self.assertFalse(self.master.email_verified)

    def test_decode_uid_returns_none_for_garbage(self):
        for junk in ('', '!!!', '////', 'é'):
            with self.subTest(junk=junk):
                self.assertIsNone(decode_uid(junk))


class ResendVerificationTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com')

    def test_requires_login(self):
        self.assertTrue(self.client.get('/auth/resend-verification/')['Location'].startswith('/auth/login/'))

    def test_sends_a_link_that_works(self):
        self.client.force_login(self.master.user)
        response = self.client.get('/auth/resend-verification/')
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r'(/auth/verify-email/[^/\s]+/[^/\s]+/)', mail.outbox[0].body).group(1)
        self.assertTrue(self.client.get(path).context['success'])

    def test_already_verified_sends_nothing(self):
        self.master.email_verified = True
        self.master.save()
        self.client.force_login(self.master.user)
        self.client.get('/auth/resend-verification/')
        self.assertEqual(len(mail.outbox), 0)
