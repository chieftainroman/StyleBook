"""
Tests for "Forgot password?" — /auth/forgot-password/ and the link it emails.
"""
import re

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.factories import make_master


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com', password='old-pass-123')

    def test_page_renders(self):
        self.assertTemplateUsed(self.client.get('/auth/forgot-password/'), 'accounts/forgot_password.html')

    def test_empty_email_shows_an_error(self):
        response = self.client.post('/auth/forgot-password/', {'email': '  '})
        self.assertRedirects(response, '/auth/forgot-password/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)

    def test_known_email_gets_exactly_one_reset_link(self):
        self.client.post('/auth/forgot-password/', {'email': 'ANA@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@example.com'])
        self.assertRegex(mail.outbox[0].body, r'/auth/reset-password/[^/\s]+/[^/\s]+/')

    def test_unknown_email_sends_nothing_but_shows_the_same_message(self):
        """Same message either way, so nobody can find out which emails have accounts."""
        known = self.client.post('/auth/forgot-password/', {'email': 'ana@example.com'}, follow=True)
        unknown = self.client.post('/auth/forgot-password/', {'email': 'nobody@example.com'}, follow=True)
        self.assertEqual(len(mail.outbox), 1)
        known_msg = [str(m) for m in known.context['messages']][0].replace('ana@example.com', 'X')
        unknown_msg = [str(m) for m in unknown.context['messages']][0].replace('nobody@example.com', 'X')
        self.assertEqual(known_msg, unknown_msg)


class ResetPasswordTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com', password='old-pass-123')
        self.user = self.master.user
        self.url = self.reset_url(self.user)

    def reset_url(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return f'/auth/reset-password/{uid}/{default_token_generator.make_token(user)}/'

    def post(self, new, confirm=None):
        return self.client.post(self.url, {'new_password': new, 'new_password2': new if confirm is None else confirm})

    def test_valid_link_shows_the_form(self):
        self.assertTemplateUsed(self.client.get(self.url), 'accounts/reset_password.html')

    def test_link_from_the_email_works(self):
        self.client.post('/auth/forgot-password/', {'email': 'ana@example.com'})
        path = re.search(r'(/auth/reset-password/[^/\s]+/[^/\s]+/)', mail.outbox[0].body).group(1)
        self.assertTemplateUsed(self.client.get(path), 'accounts/reset_password.html')

    def test_broken_links_show_the_invalid_page(self):
        good_uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        for url in (
            '/auth/reset-password/!!!/abc/',                                         # garbage uid
            f'/auth/reset-password/{urlsafe_base64_encode(b"99999")}/abc-def/',      # no such user
            f'/auth/reset-password/{good_uid}/wrong-token/',                         # tampered token
        ):
            with self.subTest(url=url):
                self.assertTemplateUsed(self.client.get(url), 'accounts/reset_invalid.html')

    def test_password_shorter_than_8_is_refused(self):
        self.post('short')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('old-pass-123'))

    def test_passwords_that_do_not_match_are_refused(self):
        self.post('new-pass-123', confirm='new-pass-124')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('old-pass-123'))

    def test_success_changes_the_password(self):
        response = self.post('new-pass-123')
        self.assertRedirects(response, '/auth/login/', fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('new-pass-123'))
        self.assertFalse(self.user.check_password('old-pass-123'))

    def test_you_can_log_in_with_the_new_password(self):
        self.post('new-pass-123')
        self.client.post('/auth/login/', {'username': 'ana', 'password': 'new-pass-123'})
        self.assertIn('_auth_user_id', self.client.session)

    def test_link_only_works_once(self):
        self.post('new-pass-123')
        self.assertTemplateUsed(self.client.get(self.url), 'accounts/reset_invalid.html')
