"""
Bugs found before launch, on the profile/portfolio side.
Tests tagged `known_bug` fail until their fix is applied (see accounts/tests/test_bugs.py).
"""
import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, tag

from accounts.models import Service
from bookings.models import Booking
from core.factories import day_at, future_day, make_booking, make_master, make_service


class PortfolioBugs(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master, minutes=30)
        self.lenient = Client(raise_request_exception=False)   # shows a 500 as a response instead of crashing the test
        self.lenient.force_login(self.master.user)

    def post_json(self, url, payload):
        return self.lenient.post(url, data=json.dumps(payload), content_type='application/json')

    # ── Bug 3 ────────────────────────────────────────────────────────────
    @tag('known_bug')
    def test_bug03_deleting_a_service_with_bookings_hides_it_instead_of_crashing(self):
        """
        Booking.service is on_delete=PROTECT, so deleting a service that was
        ever booked raises ProtectedError → 500. Correct: hide it
        (is_active=False) and keep the booking history.
        """
        make_booking(self.master, self.cut, day_at(future_day(), '10:00'))
        response = self.lenient.post(f'/profile/service/{self.cut.pk}/delete/')
        self.assertEqual(response.status_code, 302)
        self.cut.refresh_from_db()
        self.assertFalse(self.cut.is_active)
        self.assertEqual(Booking.objects.filter(service=self.cut).count(), 1)

    # ── Bug 13: bad input or a failing outside service shows a server error ──
    @tag('known_bug')
    def test_bug13c_price_nan_is_refused_not_a_crash(self):
        """Decimal('NaN') can't be compared with <, so the price check itself crashes."""
        response = self.lenient.post('/profile/service/add/', {'name': 'Odd', 'duration_minutes': '30', 'price': 'NaN'})
        self.assertNotEqual(response.status_code, 500)
        self.assertFalse(Service.objects.filter(name='Odd').exists())

    @tag('known_bug')
    def test_bug13d_malformed_preset_import_is_400_not_a_crash(self):
        for payload in ([1, 2, 3], {'services': ['Haircut']}, {'services': 'Haircut'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post_json('/profile/service/add/', payload).status_code, 400)

    @tag('known_bug')
    def test_bug13e_malformed_reorder_is_400_not_a_crash(self):
        for payload in ({'ids': ['abc']}, {'ids': 'abc'}, [1, 2]):
            with self.subTest(payload=payload):
                self.assertEqual(self.post_json('/profile/service/reorder/', payload).status_code, 400)

    @tag('known_bug')
    def test_bug13f_service_photo_reports_cloudinary_failure(self):
        """The other upload endpoints answer 502 with a message; this one crashes."""
        with mock.patch('cloudinary.uploader.upload', side_effect=ConnectionError('cloudinary down')):
            response = self.lenient.post('/profile/service/upload-photo/',
                                         {'file': SimpleUploadedFile('a.jpg', b'jpg', content_type='image/jpeg')})
        self.assertEqual(response.status_code, 502)

    @tag('known_bug')
    def test_bug13g_instagram_page_survives_a_bad_reservation_id(self):
        self.assertEqual(self.lenient.get('/instagram/?reservation_id=abc').status_code, 200)

    # ── Bug 14 ───────────────────────────────────────────────────────────
    @tag('known_bug')
    def test_bug14_profile_client_count_comes_from_real_bookings(self):
        """
        The public profile's "clients" number counts the OLD Reservation
        table, so a master with real bookings shows 0. Correct: distinct
        clients with a confirmed or completed booking.
        """
        day = future_day()
        make_booking(self.master, self.cut, day_at(day, '09:00'), email='jordan@example.com')
        make_booking(self.master, self.cut, day_at(day, '10:00'), email='JORDAN@example.com',
                     status=Booking.STATUS_COMPLETED)                                  # same person
        make_booking(self.master, self.cut, day_at(day, '11:00'), email='sam@example.com',
                     status=Booking.STATUS_COMPLETED)
        make_booking(self.master, self.cut, day_at(day, '12:00'), email='pat@example.com',
                     status=Booking.STATUS_CANCELLED)                                  # doesn't count
        make_booking(self.master, self.cut, day_at(day, '13:00'), email='kim@example.com',
                     status=Booking.STATUS_PENDING_OTP)                                # never confirmed
        other = make_master('ben')
        make_booking(other, make_service(other), day_at(day, '09:00'), email='zed@example.com')
        self.assertEqual(self.client.get('/profile/ana/').context['client_count'], 2)
