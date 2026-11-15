"""
Tests for what a logged-in master does with bookings, and — most
importantly — that one master can never see or change another master's
bookings by guessing a reference code.
"""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from PIL import Image

from bookings.models import Booking
from core.factories import day_at, future_day, make_booking, make_master, make_service


class MasterTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master, minutes=30, price='40.00')
        self.day = future_day(7)
        self.booking = make_booking(self.master, self.cut, day_at(self.day, '10:00'), email='jordan@example.com')
        self.client.force_login(self.master.user)

        # A second master whose data must stay invisible to 'ana'
        self.rival = make_master('ben')
        self.rival_booking = make_booking(self.rival, make_service(self.rival), day_at(self.day, '10:00'),
                                          email='secret@example.com')

    def refresh(self, booking=None):
        booking = booking or self.booking
        booking.refresh_from_db()
        return booking


class LoginRequiredTests(TestCase):
    def test_master_pages_redirect_anonymous_visitors_to_login(self):
        for url in ('/dashboard/', '/reservations/', '/reservations/STBK-ABCDE/', '/my-qr/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith('/auth/login/'))

    def test_master_post_actions_redirect_anonymous_visitors_to_login(self):
        for url in ('/reservations/STBK-ABCDE/status/', '/reservations/STBK-ABCDE/cancel/',
                    '/reservations/STBK-ABCDE/notes/'):
            with self.subTest(url=url):
                self.assertTrue(self.client.post(url)['Location'].startswith('/auth/login/'))


class OwnershipTests(MasterTestCase):
    """Every master-side booking URL must 404 for someone else's booking."""

    def test_cannot_view_another_masters_booking(self):
        self.assertEqual(self.client.get(f'/reservations/{self.rival_booking.reference_code}/').status_code, 404)

    def test_cannot_change_status_cancel_or_annotate_another_masters_booking(self):
        ref = self.rival_booking.reference_code
        self.assertEqual(self.client.post(f'/reservations/{ref}/status/', {'status': 'completed'}).status_code, 404)
        self.assertEqual(self.client.post(f'/reservations/{ref}/cancel/').status_code, 404)
        self.assertEqual(self.client.post(f'/reservations/{ref}/notes/', {'master_notes': 'hi'}).status_code, 404)
        booking = self.refresh(self.rival_booking)
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(booking.master_notes, '')

    def test_reservations_list_and_dashboard_only_show_own_bookings(self):
        response = self.client.get('/reservations/?tab=all')
        self.assertEqual(list(response.context['bookings']), [self.booking])
        self.assertNotContains(response, 'secret@example.com')
        self.assertEqual(self.client.get('/dashboard/').context['total_clients'], 1)


class BookingDetailTests(MasterTestCase):
    def test_detail_shows_the_clients_earlier_visits(self):
        earlier = make_booking(self.master, self.cut, timezone.now() - timedelta(days=30),
                               email='JORDAN@example.com', status=Booking.STATUS_COMPLETED)
        response = self.client.get(f'/reservations/{self.booking.reference_code}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['client_history']), [earlier])

    def test_unknown_reference_is_404(self):
        self.assertEqual(self.client.get('/reservations/STBK-NOPE2/').status_code, 404)


class ChangeStatusTests(MasterTestCase):
    def post_status(self, status):
        return self.client.post(f'/reservations/{self.booking.reference_code}/status/', {'status': status})

    def test_master_can_mark_completed_no_show_and_back_to_confirmed(self):
        for status in (Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW, Booking.STATUS_CONFIRMED):
            with self.subTest(status=status):
                self.assertRedirects(self.post_status(status), f'/reservations/{self.booking.reference_code}/',
                                     fetch_redirect_response=False)
                self.assertEqual(self.refresh().status, status)

    def test_other_statuses_are_refused(self):
        for status in ('cancelled', 'pending_otp', 'refused', 'deleted', ''):
            with self.subTest(status=status):
                self.post_status(status)
                self.assertEqual(self.refresh().status, Booking.STATUS_CONFIRMED)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(f'/reservations/{self.booking.reference_code}/status/').status_code, 405)


class MasterCancelTests(MasterTestCase):
    def test_master_cancel_notifies_the_client_with_the_reason(self):
        self.client.post(f'/reservations/{self.booking.reference_code}/cancel/', {'reason': 'Shop flooded'})
        booking = self.refresh()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jordan@example.com'])
        self.assertIn('Shop flooded', mail.outbox[0].body)

    def test_completed_or_no_show_bookings_cannot_be_cancelled(self):
        for status in (Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW, Booking.STATUS_CANCELLED):
            with self.subTest(status=status):
                Booking.objects.filter(pk=self.booking.pk).update(status=status)
                self.client.post(f'/reservations/{self.booking.reference_code}/cancel/')
                self.assertEqual(self.refresh().status, status)
        self.assertEqual(len(mail.outbox), 0)


class NotesTests(MasterTestCase):
    def test_notes_are_saved_and_capped_at_2000_characters(self):
        self.client.post(f'/reservations/{self.booking.reference_code}/notes/', {'master_notes': '  Likes it short  '})
        self.assertEqual(self.refresh().master_notes, 'Likes it short')
        self.client.post(f'/reservations/{self.booking.reference_code}/notes/', {'master_notes': 'x' * 3000})
        self.assertEqual(len(self.refresh().master_notes), 2000)


class ReservationsPageTests(MasterTestCase):
    def setUp(self):
        super().setUp()
        self.pending = make_booking(self.master, self.cut, day_at(self.day, '11:00'), status=Booking.STATUS_PENDING_OTP)
        self.past = make_booking(self.master, self.cut, timezone.now() - timedelta(days=2),
                                 status=Booking.STATUS_COMPLETED)
        self.cancelled = make_booking(self.master, self.cut, day_at(self.day, '12:00'),
                                      status=Booking.STATUS_CANCELLED)

    def tab(self, name):
        return set(self.client.get(f'/reservations/?tab={name}').context['bookings'])

    def test_tabs_sort_bookings_into_the_right_bucket(self):
        self.assertEqual(self.tab('upcoming'), {self.booking, self.pending})
        self.assertEqual(self.tab('past'), {self.past})
        self.assertEqual(self.tab('cancelled'), {self.cancelled})
        self.assertEqual(self.tab('all'), {self.booking, self.pending, self.past, self.cancelled})

    def test_unknown_tab_falls_back_to_upcoming(self):
        self.assertEqual(self.client.get('/reservations/?tab=../../etc').context['tab'], 'upcoming')

    def test_counts_match_the_tabs(self):
        counts = self.client.get('/reservations/').context['counts']
        self.assertEqual(counts, {'upcoming': 2, 'past': 1, 'cancelled': 1, 'all': 4})

    def test_calendar_week_view_puts_bookings_on_the_right_day(self):
        response = self.client.get(f'/reservations/?view=calendar&week={self.day.isoformat()}')
        self.assertEqual(response.status_code, 200)
        week = response.context['week_data']
        self.assertEqual(week['start'].weekday(), 0)                     # always starts Monday
        day = next(d for d in week['days'] if d['date'] == self.day)
        self.assertEqual(set(day['bookings']), {self.booking, self.pending})   # cancelled hidden

    def test_calendar_with_a_bad_week_param_shows_this_week(self):
        response = self.client.get('/reservations/?view=calendar&week=garbage')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['week_data']['start'], response.context['week_data']['this_week'])


class DashboardTests(MasterTestCase):
    def test_revenue_counts_only_completed_bookings_this_month(self):
        today = timezone.now().replace(hour=0, minute=1, second=0, microsecond=0)
        make_booking(self.master, self.cut, today, status=Booking.STATUS_COMPLETED)              # 40
        trim = make_service(self.master, 'Beard', minutes=15, price='25.00')
        make_booking(self.master, trim, today, status=Booking.STATUS_COMPLETED)                  # 25
        make_booking(self.master, self.cut, today, status=Booking.STATUS_NO_SHOW)                # not revenue
        make_booking(self.master, self.cut, today, status=Booking.STATUS_CANCELLED)              # not revenue
        make_booking(self.rival, self.rival_booking.service, today, status=Booking.STATUS_COMPLETED)  # not ana's

        context = self.client.get('/dashboard/').context
        self.assertEqual(context['revenue_month'], Decimal('65.00'))
        self.assertEqual(context['avg_booking_value'], Decimal('32.50'))

    def test_new_master_with_no_bookings_sees_zeros_not_errors(self):
        newbie = make_master('newbie')
        self.client.force_login(newbie.user)
        context = self.client.get('/dashboard/').context
        self.assertEqual(context['revenue_month'], 0)
        self.assertEqual(context['return_rate'], 0)
        self.assertFalse(context['is_open_for_bookings'])

    def test_booking_link_points_to_the_masters_page(self):
        self.assertTrue(self.client.get('/dashboard/').context['booking_url'].endswith('/book/ana/'))


class QrCodeTests(MasterTestCase):
    def test_qr_is_a_png_of_the_requested_size(self):
        response = self.client.get('/qr/ana.png?size=300')
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(Image.open(BytesIO(response.content)).size, (300, 300))

    def test_size_is_clamped_so_nobody_can_request_a_huge_image(self):
        for asked, expected in (('99999', 1200), ('1', 120), ('abc', 400)):
            with self.subTest(size=asked):
                response = self.client.get(f'/qr/ana.png?size={asked}')
                self.assertEqual(Image.open(BytesIO(response.content)).size, (expected, expected))

    def test_download_flag_sets_attachment_header(self):
        self.assertIn('attachment', self.client.get('/qr/ana.png?download=1')['Content-Disposition'])

    def test_unknown_user_is_404(self):
        self.assertEqual(self.client.get('/qr/nobody.png').status_code, 404)

    def test_qr_page_renders_for_the_master(self):
        self.assertEqual(self.client.get('/my-qr/').status_code, 200)
