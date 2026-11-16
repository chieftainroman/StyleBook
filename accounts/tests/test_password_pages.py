"""
Tests for django-allauth's password-reset pages (the "Forgot password?" link
on the login page goes here), the Google sign-in message pages, and the
404/500 pages. All of them use templates/account/_auth_base.html.
"""
import re

from django.core import mail
from django.template.loader import render_to_string
from django import forms
from django.test import TestCase

from core.factories import make_master

DESIGN_MARK = 'SHOWPIECE'          # the Anton logo in _auth_base.html


class AllauthPasswordResetFlowTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com', password='old-pass-123')

    def request_link(self):
        self.client.post('/accounts/password/reset/', {'email': 'ana@example.com'})
        body = mail.outbox[-1].body
        return re.search(r'https?://[^/\s]+(/accounts/password/reset/key/[^\s]+/)', body).group(1)

    def test_request_page_uses_the_new_design(self):
        response = self.client.get('/accounts/password/reset/')
        self.assertContains(response, DESIGN_MARK)
        self.assertContains(response, 'name="email"')

    def test_requesting_a_link_shows_check_your_email(self):
        response = self.client.post('/accounts/password/reset/', {'email': 'ana@example.com'}, follow=True)
        self.assertContains(response, 'Check your email')
        self.assertEqual(len(mail.outbox), 1)

    def test_whole_flow_ends_on_a_real_page_and_the_new_password_works(self):
        link = self.request_link()
        form_page = self.client.get(link, follow=True)               # allauth redirects to a "set-password" URL
        self.assertContains(form_page, 'name="password1"')
        self.assertContains(form_page, DESIGN_MARK)

        done = self.client.post(form_page.redirect_chain[-1][0] if form_page.redirect_chain else link,
                                {'password1': 'brand-new-pass-9', 'password2': 'brand-new-pass-9'}, follow=True)
        self.assertContains(done, 'Password changed')                 # used to be an empty page
        self.assertContains(done, DESIGN_MARK)

        self.master.user.refresh_from_db()
        self.assertTrue(self.master.user.check_password('brand-new-pass-9'))
        self.client.logout()
        self.client.post('/auth/login/', {'username': 'ana', 'password': 'brand-new-pass-9'})
        self.assertIn('_auth_user_id', self.client.session)

    def test_mismatched_passwords_show_an_error_and_change_nothing(self):
        link = self.request_link()
        form_page = self.client.get(link, follow=True)
        url = form_page.redirect_chain[-1][0] if form_page.redirect_chain else link
        response = self.client.post(url, {'password1': 'brand-new-pass-9', 'password2': 'different-pass-9'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lg-field-error')
        self.master.user.refresh_from_db()
        self.assertTrue(self.master.user.check_password('old-pass-123'))

    def test_broken_link_says_so_and_offers_a_new_one(self):
        response = self.client.get('/accounts/password/reset/key/abc-def/', follow=True)
        self.assertContains(response, 'Link expired')
        self.assertContains(response, 'Send a new link')

    def test_done_page_is_never_blank(self):
        self.assertContains(self.client.get('/accounts/password/reset/key/done/'), 'Password changed')


class MessagePagesTests(TestCase):
    def test_google_cancelled_page(self):
        response = self.client.get('/accounts/3rdparty/login/cancelled/')
        self.assertContains(response, 'Sign-in cancelled')
        self.assertContains(response, DESIGN_MARK)

    def test_google_error_page(self):
        html = render_to_string('socialaccount/authentication_error.html')
        self.assertIn("Couldn't sign you in", html)
        self.assertIn('/accounts/google/login/', html)

    def test_google_signup_form_renders_its_fields(self):
        class SignupForm(forms.Form):
            email = forms.EmailField()
        html = render_to_string('socialaccount/signup.html', {'form': SignupForm()})
        self.assertIn('name="email"', html)
        self.assertIn('Almost there', html)

    def test_404_page(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, DESIGN_MARK, status_code=404)

    def test_500_page_renders_on_its_own(self):
        """Django renders 500.html with no request and no context, so it must not need either."""
        html = render_to_string('500.html')
        self.assertIn('Something went wrong', html)
        self.assertNotIn("We've been notified", html)       # nothing notifies anyone, so don't claim it
