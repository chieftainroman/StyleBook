"""
Safety net: open every page in the app and make sure none of them crashes.

This catches the most embarrassing kind of bug: a typo in a template or a
missing variable that turns a page into "Server Error (500)". If you add a
new page, add its URL to one of the lists below.
"""
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import Client, TestCase

from allauth.socialaccount.models import SocialApp
from bookings.tokens import make_action_token
from core.factories import day_at, future_day, make_booking, make_master, make_service

OK = (200, 301, 302)


class EveryPageTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master)
        self.booking = make_booking(self.master, self.cut, day_at(future_day(), '10:00'))
        self.cancel = make_action_token(self.booking.reference_code, 'cancel')
        self.resched = make_action_token(self.booking.reference_code, 'reschedule')
        self.browser = Client(raise_request_exception=False)    # report a crash as a 500 instead of stopping

    def assert_pages_load(self, urls):
        for url in urls:
            with self.subTest(url=url):
                response = self.browser.get(url)
                self.assertIn(response.status_code, OK, f'{url} answered {response.status_code}')


class PublicPagesTests(EveryPageTestCase):
    def test_every_public_page_loads(self):
        d = future_day().isoformat()
        self.assert_pages_load([
            '/', '/auth/login/', '/auth/register/', '/auth/forgot-password/',
            '/profile/ana/', '/book/ana/', '/book/ana/?src=qr', '/qr/ana.png',
            f'/book/ana/api/availability/?service_id={self.cut.id}&date={d}',
            f'/book/ana/api/summary/?service_id={self.cut.id}',
            f'/manage/cancel/{self.cancel}/', f'/manage/reschedule/{self.resched}/',
            f'/manage/reschedule/{self.resched}/api/slots/?date={d}',
            f'/manage/reschedule/{self.resched}/api/summary/',
            '/manage/cancel/not-a-real-token/', '/accounts/login/', '/admin/login/',
        ])

    def test_private_pages_send_visitors_to_login_instead_of_crashing(self):
        for url in ('/dashboard/', '/reservations/', '/profile/', '/profile/edit/', '/portfolio/',
                    '/instagram/', '/my-qr/', '/onboarding/', f'/reservations/{self.booking.reference_code}/'):
            with self.subTest(url=url):
                response = self.browser.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith('/auth/login/'))

    def test_unknown_address_shows_your_404_page(self):
        response = self.browser.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')


class MasterPagesTests(EveryPageTestCase):
    def test_every_page_a_master_uses_loads(self):
        self.browser.force_login(self.master.user)
        ref = self.booking.reference_code
        self.assert_pages_load([
            '/dashboard/', '/reservations/', '/reservations/?tab=past', '/reservations/?tab=cancelled',
            '/reservations/?tab=all', '/reservations/?view=calendar', f'/reservations/{ref}/',
            '/profile/', '/profile/ana/', '/profile/edit/', '/profile/edit/?tab=services',
            '/profile/edit/?tab=experience', '/profile/edit/?tab=certificates', '/profile/edit/?tab=honors',
            '/portfolio/', '/instagram/', '/my-qr/', '/profile/service/presets/', '/onboarding/',
            '/book/ana/', '/', '/auth/logout/',
        ])

    def test_brand_new_account_pages_load(self):
        """A just-registered master with an empty profile: nothing may crash."""
        user = User.objects.create_user('newbie', 'newbie@example.com', 'secret-123')
        self.browser.force_login(user)
        self.assert_pages_load([f'/onboarding/?step={n}' for n in range(1, 6)] + ['/dashboard/', '/book/newbie/'])

    def test_master_with_lots_of_data_pages_load(self):
        from bookings.models import Booking
        for i, status in enumerate([s for s, _ in Booking.STATUS_CHOICES]):
            make_booking(self.master, self.cut, day_at(future_day(1 + i), '11:00'), status=status,
                         email=f'client{i}@example.com')
        self.browser.force_login(self.master.user)
        self.assert_pages_load(['/dashboard/', '/reservations/?tab=all', '/reservations/?view=calendar'])


class GoogleLoginTests(TestCase):
    def test_google_login_works_once_the_social_app_is_set_up(self):
        """
        After a database rebuild, Google sign-in needs a "Social application"
        row in Django admin. This is what that row must look like.
        """
        app = SocialApp.objects.create(provider='google', name='Google', client_id='test-id', secret='test-secret')
        app.sites.add(Site.objects.get_current())
        response = self.client.get('/accounts/google/login/')
        self.assertIn(response.status_code, OK)
