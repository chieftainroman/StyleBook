"""
Bugs found before launch, in bookings.

A test tagged `known_bug` FAILS on purpose: it describes the correct
behaviour, and the bug is still in the code. Each fix patch removes the tag
from its own tests, so from then on they run with everything else.

    python manage.py test --settings=core.settings_test --tag=known_bug          # only the open bugs
    python manage.py test --settings=core.settings_test --exclude-tag=known_bug  # everything else
"""
import json
import re
from datetime import timedelta
from unittest import mock
from urllib.parse import quote

from django.conf import settings
from django.core import mail
from django.test import Client, TestCase, tag
from django.utils import timezone

from bookings import tokens
from bookings.models import Booking, OTPRequest
from bookings.slots import get_available_slots
from bookings.tokens import make_action_token
from core.factories import day_at, future_day, make_booking, make_master, make_service


class BookingBugs(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master, minutes=30)
        self.day = future_day(7)
        self.slot = day_at(self.day, '10:00')
        self.lenient = Client(raise_request_exception=False)   # shows a 500 as a response instead of crashing the test

    def post_json(self, url, payload, client=None):
        return (client or self.client).post(url, data=json.dumps(payload), content_type='application/json')

    def create(self, email, start=None, client=None):
        return self.post_json('/book/ana/create/', {
            'service_id': self.cut.id, 'slot_iso': (start or self.slot).isoformat(),
            'client_name': 'Someone', 'client_email': email,
        }, client=client)

    def verify(self, ref):
        code = OTPRequest.objects.filter(booking__reference_code=ref).order_by('-created_at', '-id').first().code
        return self.post_json('/book/ana/verify-otp/', {'reference_code': ref, 'code': code})

    # ── Bug 1 ────────────────────────────────────────────────────────────
    def test_bug01_abandoned_pending_booking_releases_the_slot(self):
        """
        A client starts booking, then never enters the code (closed the tab,
        typo'd their email). Today that `pending_otp` booking blocks the slot
        FOREVER. Correct: a pending hold expires after 15 minutes.
        """
        ghost = make_booking(self.master, self.cut, self.slot, status=Booking.STATUS_PENDING_OTP,
                             email='typo@gmial.com')
        Booking.objects.filter(pk=ghost.pk).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertIn(self.slot, get_available_slots(self.master, self.cut, self.day))

    def test_bug01b_late_code_cannot_double_book_a_slot_someone_else_took(self):
        """
        Guard for the bug 1 fix: once the hold has expired and someone else has
        booked the slot, the first client's late code must not confirm a
        second booking into it.
        """
        first = self.create('slow@example.com').json()['reference_code']
        Booking.objects.filter(reference_code=first).update(created_at=timezone.now() - timedelta(hours=1))

        second = self.create('fast@example.com').json().get('reference_code')
        self.assertIsNotNone(second, 'slot should be bookable once the old hold expired')
        self.assertEqual(self.verify(second).status_code, 200)

        self.post_json('/book/ana/resend-otp/', {'reference_code': first})
        response = self.verify(first)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Booking.objects.filter(start_time=self.slot, status=Booking.STATUS_CONFIRMED).count(), 1)

    # ── Bug 2 ────────────────────────────────────────────────────────────
    def test_bug02_server_clock_uses_new_york_time(self):
        """
        settings.py sets neither TIME_ZONE nor USE_TZ, so Django 4.2 runs on
        naive America/Chicago time. For NYC masters "now" is an hour behind:
        a 2h lead time is really 1h, and with lead time 0 clients can book
        slots that already passed. Correct: TIME_ZONE = 'America/New_York'.
        """
        self.assertEqual(settings.TIME_ZONE, 'America/New_York')

    # ── Bug 4 ────────────────────────────────────────────────────────────
    def test_bug04_cancel_link_still_works_for_a_booking_two_months_out(self):
        """
        Clients may book up to 90 days ahead, but the cancel/reschedule links
        in the confirmation email expire after 30 days. Correct: links stay
        valid until the appointment.
        """
        far_day = future_day(60)
        ref = self.create('planner@example.com', start=day_at(far_day, '10:00')).json()['reference_code']
        self.verify(ref)
        body = next(m for m in mail.outbox if m.to == ['planner@example.com'] and 'confirmed' in m.subject).body
        cancel_path = re.search(r'https?://[^/\s]+(/manage/cancel/[^/\s"]+/)', body).group(1)

        in_45_days = tokens.time.time() + 45 * 24 * 3600
        with mock.patch.object(tokens.time, 'time', return_value=in_45_days):
            response = self.client.get(cancel_path)
        self.assertTemplateUsed(response, 'bookings/client_cancel_confirm.html')

    # ── Bug 5 ────────────────────────────────────────────────────────────
    def test_bug05_master_cannot_revive_a_cancelled_booking_into_a_double_booking(self):
        """
        The status endpoint allows → 'confirmed' from ANY state. After a
        client cancels and someone else takes the slot, the master can flip
        the old booking back to confirmed: two clients, capacity 1.
        Correct: cancelled/refused bookings can't be changed back.
        """
        old = make_booking(self.master, self.cut, self.slot, status=Booking.STATUS_CANCELLED, email='a@example.com')
        make_booking(self.master, self.cut, self.slot, email='b@example.com')
        self.client.force_login(self.master.user)
        self.client.post(f'/reservations/{old.reference_code}/status/', {'status': 'confirmed'})
        old.refresh_from_db()
        self.assertEqual(old.status, Booking.STATUS_CANCELLED)

    # ── Bug 8 ────────────────────────────────────────────────────────────
    def test_bug08_client_can_move_their_booking_15_minutes_later(self):
        """
        When rescheduling, the client's OWN booking still counts as taking the
        slot, so "move me from 10:00 to 10:15" is refused as unavailable.
        Correct: the booking being moved doesn't block itself.
        """
        booking = make_booking(self.master, self.cut, self.slot)
        token = make_action_token(booking.reference_code, 'reschedule')
        self.client.post(f'/manage/reschedule/{token}/', {'slot_iso': day_at(self.day, '10:15').isoformat()})
        booking.refresh_from_db()
        self.assertEqual(booking.start_time, day_at(self.day, '10:15'))

    # ── Bug 9 ────────────────────────────────────────────────────────────
    @tag('known_bug')
    def test_bug09_simultaneous_requests_cannot_double_book(self):
        """
        create_booking checks availability, THEN inserts, with nothing locking
        the slot in between. Two clients pressing "Book" at the same moment
        both pass the check. Simulated here: the availability check returns a
        stale answer (as it would for the second request in a real race).
        Correct: a final check inside the transaction, under a row lock.
        """
        make_booking(self.master, self.cut, self.slot, email='first@example.com')
        with mock.patch('bookings.views.get_available_slots', return_value=[self.slot]):
            response = self.create('second@example.com')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Booking.objects.filter(start_time=self.slot).count(), 1)

    # ── Bug 10 ───────────────────────────────────────────────────────────
    @tag('known_bug')
    def test_bug10_garbled_link_shows_the_invalid_page_not_a_500(self):
        """
        A link with a non-ASCII character (e.g. mangled by an email client)
        makes hmac.compare_digest raise TypeError → 500.
        Correct: the normal "link unavailable" page.
        """
        booking = make_booking(self.master, self.cut, self.slot)
        real = make_action_token(booking.reference_code, 'cancel')
        mangled = real[:-1] + 'ü'                     # last character mangled in transit
        response = self.lenient.get(f'/manage/cancel/{quote(mangled)}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/client_action_invalid.html')

    # ── Bug 15 ───────────────────────────────────────────────────────────
    def test_bug15_client_is_told_when_the_code_email_cannot_be_sent(self):
        """
        If the code email fails, the page still says "code sent" and the
        client waits for an email that never comes, while the slot is held.
        Correct: an error the client can act on, and the slot released.
        """
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError('smtp down')):
            response = self.create('jordan@example.com', client=self.lenient)
        self.assertEqual(response.status_code, 502)
        self.assertIn('email', response.json()['error'].lower())
        self.assertIn(self.slot, get_available_slots(self.master, self.cut, self.day))

    # ── Bug 17 ───────────────────────────────────────────────────────────
    def test_bug17_link_unavailable_page_says_why(self):
        """
        The view works out WHY a link can't be used, but the page ignores it
        and shows one generic sentence. Correct: the reason is on the page.
        """
        booking = make_booking(self.master, self.cut, timezone.now() - timedelta(hours=2))
        response = self.client.get(f'/manage/cancel/{make_action_token(booking.reference_code, "cancel")}/')
        self.assertContains(response, 'already happened')
        cancelled = make_booking(self.master, self.cut, self.slot, status=Booking.STATUS_CANCELLED)
        response = self.client.get(f'/manage/cancel/{make_action_token(cancelled.reference_code, "cancel")}/')
        self.assertContains(response, 'cancelled')
