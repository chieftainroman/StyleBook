"""Tests for /auth/register/ — creating a master account with a password."""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import MasterProfile
from core.factories import make_master

GOOD = {
    'username': 'ana', 'email': 'ana@example.com', 'password': 'secret-123',
    'specialty': 'barber', 'location': 'Brooklyn', 'years_exp': '4',
    'ig_handle': 'ana.cuts', 'bio': 'Fades, tapers and beard work.',
}


class RegisterTests(TestCase):
    def register(self, **overrides):
        return self.client.post('/auth/register/', {**GOOD, **overrides})

    def test_register_page_renders(self):
        self.assertTemplateUsed(self.client.get('/auth/register/'), 'register.html')

    def test_success_creates_user_and_profile_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        user = User.objects.get(username='ana')
        self.assertIn('_auth_user_id', self.client.session)
        profile = MasterProfile.objects.get(user=user)
        self.assertEqual((profile.specialty, profile.location, profile.years_exp, profile.ig_handle),
                         ('barber', 'Brooklyn', 4, 'ana.cuts'))

    def test_password_is_stored_hashed_not_as_plain_text(self):
        self.register()
        user = User.objects.get(username='ana')
        self.assertNotEqual(user.password, 'secret-123')
        self.assertTrue(user.check_password('secret-123'))

    def test_exactly_one_profile_is_created(self):
        self.register()
        self.assertEqual(MasterProfile.objects.filter(user__username='ana').count(), 1)

    def test_missing_username_email_or_password_creates_nothing(self):
        for field in ('username', 'email', 'password'):
            with self.subTest(missing=field):
                response = self.register(**{field: ''})
                self.assertRedirects(response, '/auth/register/', fetch_redirect_response=False)
        self.assertFalse(User.objects.exists())

    def test_password_shorter_than_6_is_refused(self):
        self.register(password='12345')
        self.assertFalse(User.objects.exists())

    def test_taken_username_is_refused(self):
        make_master('ana', email='someone-else@example.com')
        self.register()
        self.assertEqual(User.objects.filter(username='ana').count(), 1)
        self.assertFalse(User.objects.filter(email='ana@example.com').exists())

    def test_taken_email_is_refused(self):
        make_master('other', email='ana@example.com')
        self.register()
        self.assertFalse(User.objects.filter(username='ana').exists())

    def test_years_that_are_not_a_number_become_zero(self):
        self.register(years_exp='lots')
        self.assertEqual(User.objects.get(username='ana').profile.years_exp, 0)

    def test_without_a_specialty_you_go_to_onboarding(self):
        response = self.register(specialty='')
        self.assertRedirects(response, '/onboarding/', fetch_redirect_response=False)

    def test_already_logged_in_visitor_is_sent_to_dashboard(self):
        self.client.force_login(make_master('ben').user)
        self.assertRedirects(self.client.get('/auth/register/'), '/dashboard/', fetch_redirect_response=False)
