"""
Tests for the client's email links (no login needed):

    /manage/cancel/<token>/
    /manage/reschedule/<token>/              (+ /api/slots/ and /api/summary/)
"""
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from bookings.slots import get_available_slots
from bookings.tokens import make_action_token
from core.factories import day_at, future_day, make_booking, make_master, make_service


class ClientActionTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master, minutes=30)
        self.day = future_day(7)
        self.booking = make_booking(self.master, self.cut, day_at(self.day, '10:00'), email='jordan@example.com')
        self.cancel_url = f'/manage/cancel/{make_action_token(self.booking.reference_code, "cancel")}/'
        self.resched_token = make_action_token(self.booking.reference_code, 'reschedule')
        self.resched_url = f'/manage/reschedule/{self.resched_token}/'

    def refresh(self):
        self.booking.refresh_from_db()
        return self.booking

    def offered(self, day=None):
        return get_available_slots(self.master, self.cut, day or self.day)


class ClientCancelTests(ClientActionTestCase):
    def test_get_shows_a_confirmation_page_and_changes_nothing(self):
        response = self.client.get(self.cancel_url)
        self.assertTemplateUsed(response, 'bookings/client_cancel_confirm.html')
        self.assertEqual(self.refresh().status, Booking.STATUS_CONFIRMED)

    def test_post_cancels_and_notifies_client_and_master(self):
        response = self.client.post(self.cancel_url, {'reason': 'Sick'})
        self.assertTemplateUsed(response, 'bookings/client_cancelled_success.html')
        self.assertEqual(self.refresh().status, Booking.STATUS_CANCELLED)
        self.assertIsNotNone(self.booking.cancelled_at)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['ana@example.com', 'jordan@example.com'])

    def test_cancelling_frees_the_slot(self):
        self.assertNotIn(day_at(self.day, '10:00'), self.offered())
        self.client.post(self.cancel_url)
        self.assertIn(day_at(self.day, '10:00'), self.offered())

    def test_tampered_token_is_refused(self):
        response = self.client.post(self.cancel_url[:-3] + 'xx/')
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
        self.assertEqual(self.refresh().status, Booking.STATUS_CONFIRMED)

    def test_reschedule_token_cannot_cancel(self):
        response = self.client.post(f'/manage/cancel/{self.resched_token}/')
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
        self.assertEqual(self.refresh().status, Booking.STATUS_CONFIRMED)

    def test_token_for_a_deleted_booking_says_not_found(self):
        url = f'/manage/cancel/{make_action_token("STBK-GHST2", "cancel")}/'
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
        self.assertEqual(response.context['message'], 'Booking not found.')

    def test_finished_bookings_cannot_be_cancelled(self):
        for status in (Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED,
                       Booking.STATUS_NO_SHOW, Booking.STATUS_REFUSED):
            with self.subTest(status=status):
                Booking.objects.filter(pk=self.booking.pk).update(status=status)
                response = self.client.post(self.cancel_url)
                self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
                self.assertEqual(self.refresh().status, status)

    def test_appointment_in_the_past_cannot_be_cancelled(self):
        Booking.objects.filter(pk=self.booking.pk).update(start_time=timezone.now() - timedelta(hours=1))
        response = self.client.post(self.cancel_url)
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
        self.assertIn('already happened', response.context['message'])
        self.assertEqual(self.refresh().status, Booking.STATUS_CONFIRMED)

    def test_pending_booking_can_be_cancelled_too(self):
        Booking.objects.filter(pk=self.booking.pk).update(status=Booking.STATUS_PENDING_OTP)
        self.client.post(self.cancel_url)
        self.assertEqual(self.refresh().status, Booking.STATUS_CANCELLED)


class ClientRescheduleTests(ClientActionTestCase):
    def test_get_shows_the_picker(self):
        self.assertTemplateUsed(self.client.get(self.resched_url), 'bookings/client_reschedule_picker.html')

    def test_moving_to_a_free_slot_updates_times_and_notifies_both(self):
        new_start = day_at(self.day + timedelta(days=1), '15:00')
        response = self.client.post(self.resched_url, {'slot_iso': new_start.isoformat()})

        self.assertTemplateUsed(response, 'bookings/client_rescheduled_success.html')
        booking = self.refresh()
        self.assertEqual(booking.start_time, new_start)
        self.assertEqual(booking.end_time, new_start + timedelta(minutes=30))
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['ana@example.com', 'jordan@example.com'])

    def test_rescheduling_frees_the_old_slot_and_takes_the_new_one(self):
        new_start = day_at(self.day, '15:00')
        self.client.post(self.resched_url, {'slot_iso': new_start.isoformat()})
        slots = self.offered()
        self.assertIn(day_at(self.day, '10:00'), slots)
        self.assertNotIn(new_start, slots)

    def test_taken_slot_is_refused_and_nothing_changes(self):
        make_booking(self.master, self.cut, day_at(self.day, '15:00'), email='other@example.com')
        response = self.client.post(self.resched_url, {'slot_iso': day_at(self.day, '15:00').isoformat()})
        self.assertRedirects(response, self.resched_url, fetch_redirect_response=False)
        self.assertEqual(self.refresh().start_time, day_at(self.day, '10:00'))

    def test_garbage_or_off_hours_slot_is_refused(self):
        for bad in ('not-a-date', day_at(self.day, '22:00').isoformat(), day_at(self.day, '15:07').isoformat()):
            with self.subTest(slot=bad):
                self.client.post(self.resched_url, {'slot_iso': bad})
                self.assertEqual(self.refresh().start_time, day_at(self.day, '10:00'))

    def test_cancel_token_cannot_reschedule(self):
        cancel_token = make_action_token(self.booking.reference_code, 'cancel')
        response = self.client.post(f'/manage/reschedule/{cancel_token}/',
                                    {'slot_iso': day_at(self.day, '15:00').isoformat()})
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')
        self.assertEqual(self.refresh().start_time, day_at(self.day, '10:00'))

    def test_cancelled_booking_cannot_be_rescheduled(self):
        Booking.objects.filter(pk=self.booking.pk).update(status=Booking.STATUS_CANCELLED)
        response = self.client.post(self.resched_url, {'slot_iso': day_at(self.day, '15:00').isoformat()})
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')

    def test_slots_api(self):
        url = f'{self.resched_url}api/slots/'
        data = self.client.get(url, {'date': self.day.isoformat()}).json()
        self.assertIn('15:00', [s['time'] for s in data['slots']])
        self.assertEqual(self.client.get(url, {'date': 'soon'}).status_code, 400)
        self.assertEqual(self.client.get('/manage/reschedule/bad.token/api/slots/',
                                         {'date': self.day.isoformat()}).status_code, 400)

    def test_summary_api(self):
        data = self.client.get(f'{self.resched_url}api/summary/').json()
        self.assertEqual(len(data['availability']), 30)
        self.assertEqual(self.client.get('/manage/reschedule/bad.token/api/summary/').status_code, 400)
