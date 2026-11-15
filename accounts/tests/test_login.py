"""
Tests for /auth/login/ and /auth/logout/.

How to read a test like these: each one sets something up, does ONE thing
(a click, a form post), and checks what a real person would notice.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from core.factories import make_master


def is_logged_in(client):
    """True if the test browser currently holds a logged-in session."""
    return '_auth_user_id' in client.session


class LoginTests(TestCase):
    def setUp(self):
        self.master = make_master('ana', email='ana@example.com', password='right-pass-1')

    def login(self, username, password='right-pass-1', **extra):
        return self.client.post('/auth/login/', {'username': username, 'password': password, **extra})

    def test_login_page_renders(self):
        response = self.client.get('/auth/login/?next=/reservations/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')
        self.assertEqual(response.context['next'], '/reservations/')

    def test_login_with_username_goes_to_dashboard(self):
        response = self.login('ana')
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        self.assertTrue(is_logged_in(self.client))

    def test_login_with_email_works_whatever_the_capitals(self):
        for typed in ('ana@example.com', 'ANA@Example.com', '  ana@example.com  '):
            with self.subTest(typed=typed):
                self.client.logout()
                self.login(typed)
                self.assertTrue(is_logged_in(self.client))

    def test_wrong_password_keeps_you_logged_out(self):
        response = self.login('ana', password='wrong')
        self.assertRedirects(response, '/auth/login/', fetch_redirect_response=False)
        self.assertFalse(is_logged_in(self.client))

    def test_unknown_user_keeps_you_logged_out(self):
        self.login('nobody@example.com')
        self.assertFalse(is_logged_in(self.client))

    def test_error_message_does_not_say_which_part_was_wrong(self):
        response = self.client.post('/auth/login/', {'username': 'ana', 'password': 'wrong'}, follow=True)
        self.assertContains(response, 'Invalid email or password.')

    def test_safe_next_page_is_honoured(self):
        response = self.login('ana', next='/reservations/')
        self.assertRedirects(response, '/reservations/', fetch_redirect_response=False)

    def test_user_who_never_picked_a_specialty_goes_to_onboarding(self):
        User.objects.create_user('fresh', 'fresh@example.com', 'right-pass-1')
        response = self.login('fresh')
        self.assertRedirects(response, '/onboarding/', fetch_redirect_response=False)

    def test_already_logged_in_visitor_is_sent_to_dashboard(self):
        self.client.force_login(self.master.user)
        self.assertRedirects(self.client.get('/auth/login/'), '/dashboard/', fetch_redirect_response=False)

    def test_inactive_user_cannot_log_in(self):
        self.master.user.is_active = False
        self.master.user.save()
        self.login('ana')
        self.assertFalse(is_logged_in(self.client))


class LogoutTests(TestCase):
    def test_logout_ends_the_session_and_goes_to_login(self):
        master = make_master('ana')
        self.client.force_login(master.user)
        response = self.client.get('/auth/logout/')
        self.assertRedirects(response, '/auth/login/', fetch_redirect_response=False)
        self.assertFalse(is_logged_in(self.client))

    def test_after_logout_private_pages_ask_for_login_again(self):
        master = make_master('ana')
        self.client.force_login(master.user)
        self.client.get('/auth/logout/')
        self.assertTrue(self.client.get('/dashboard/')['Location'].startswith('/auth/login/'))
