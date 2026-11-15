"""Tests for model methods in bookings/models.py and accounts/models.py."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import DEFAULT_WORKING_HOURS, MasterProfile, UnavailableSlot
from bookings.models import Booking
from core.factories import day_at, future_day, make_booking, make_master, make_otp, make_service


class BookingModelTests(TestCase):
    def setUp(self):
        self.master = make_master()
        self.cut = make_service(self.master, minutes=45)

    def test_reference_code_format_avoids_confusing_characters(self):
        booking = make_booking(self.master, self.cut, day_at(future_day(), '10:00'))
        self.assertRegex(booking.reference_code, r'^STBK-[A-Z2-9]{5}$')
        self.assertFalse(set(booking.reference_code[5:]) & set('O0I1'))

    def test_reference_codes_are_unique(self):
        codes = {
            make_booking(self.master, self.cut, day_at(future_day(), '10:00'), email=f'c{i}@x.com').reference_code
            for i in range(40)
        }
        self.assertEqual(len(codes), 40)

    def test_end_time_is_filled_from_the_service_duration(self):
        start = day_at(future_day(), '10:00')
        booking = make_booking(self.master, self.cut, start)
        self.assertEqual(booking.end_time, start + timedelta(minutes=45))

    def test_explicit_end_time_is_not_overwritten(self):
        start = day_at(future_day(), '10:00')
        booking = make_booking(self.master, self.cut, start, end_time=start + timedelta(hours=2))
        self.assertEqual(booking.end_time, start + timedelta(hours=2))

    def test_reference_code_is_kept_on_later_saves(self):
        booking = make_booking(self.master, self.cut, day_at(future_day(), '10:00'))
        ref = booking.reference_code
        booking.client_notes = 'changed'
        booking.save()
        self.assertEqual(booking.reference_code, ref)

    def test_only_future_pending_or_confirmed_bookings_are_cancellable(self):
        future = day_at(future_day(), '10:00')
        past = timezone.now() - timedelta(hours=1)
        cases = [
            (Booking.STATUS_PENDING_OTP, future, True),
            (Booking.STATUS_CONFIRMED, future, True),
            (Booking.STATUS_CONFIRMED, past, False),
            (Booking.STATUS_CANCELLED, future, False),
            (Booking.STATUS_REFUSED, future, False),
            (Booking.STATUS_COMPLETED, future, False),
            (Booking.STATUS_NO_SHOW, future, False),
        ]
        for status, start, expected in cases:
            with self.subTest(status=status, start=start):
                booking = make_booking(self.master, self.cut, start, status=status)
                self.assertEqual(booking.is_cancellable(), expected)
                self.assertEqual(booking.is_reschedulable(), expected)


class OTPRequestModelTests(TestCase):
    def setUp(self):
        master = make_master()
        booking = make_booking(master, make_service(master), day_at(future_day(), '10:00'),
                               status=Booking.STATUS_PENDING_OTP)
        self.otp = make_otp(booking)

    def test_fresh_code_is_not_expired(self):
        self.assertFalse(self.otp.is_expired())

    def test_code_past_its_expiry_is_expired(self):
        self.otp.expires_at = timezone.now() - timedelta(seconds=1)
        self.assertTrue(self.otp.is_expired())

    def test_locks_after_exactly_five_attempts(self):
        self.otp.attempts = 4
        self.assertFalse(self.otp.is_locked())
        self.otp.attempts = 5
        self.assertTrue(self.otp.is_locked())


class MasterProfileModelTests(TestCase):
    def test_creating_a_user_creates_their_profile(self):
        user = User.objects.create_user('newbie', 'newbie@example.com', 'pw-123456')
        self.assertTrue(MasterProfile.objects.filter(user=user).exists())

    def test_open_for_bookings_needs_onboarding_and_an_active_service(self):
        master = make_master(onboarded=False)
        self.assertFalse(master.is_open_for_bookings())
        master.onboarding_completed = True
        master.save()
        self.assertFalse(master.is_open_for_bookings())            # no services yet
        service = make_service(master, active=False)
        self.assertFalse(master.is_open_for_bookings())            # only a hidden one
        service.is_active = True
        service.save()
        self.assertTrue(master.is_open_for_bookings())

    def test_is_complete_requires_every_mandatory_field(self):
        master = make_master()
        self.assertTrue(master.is_complete())
        for field, empty in (('specialty', ''), ('location', ''), ('years_exp', 0), ('bio', ''), ('phone', '')):
            with self.subTest(field=field):
                original = getattr(master, field)
                setattr(master, field, empty)
                self.assertFalse(master.is_complete())
                setattr(master, field, original)

    def test_empty_working_hours_fall_back_to_defaults(self):
        master = make_master(hours={})
        self.assertEqual(master.get_working_hours(), DEFAULT_WORKING_HOURS)


class ServiceModelTests(TestCase):
    def test_duration_display(self):
        master = make_master()
        for minutes, expected in ((45, '45min'), (60, '1h'), (90, '1h 30min'), (125, '2h 5min')):
            with self.subTest(minutes=minutes):
                self.assertEqual(make_service(master, minutes=minutes).duration_display(), expected)


class UnavailableSlotValidationTests(TestCase):
    def setUp(self):
        self.master = make_master()

    def test_recurring_block_needs_weekday_and_times(self):
        with self.assertRaises(ValidationError):
            UnavailableSlot(profile=self.master, is_recurring=True, weekday=None).clean()

    def test_recurring_block_end_must_be_after_start(self):
        from datetime import time
        with self.assertRaises(ValidationError):
            UnavailableSlot(profile=self.master, is_recurring=True, weekday=0,
                            start_time=time(14), end_time=time(13)).clean()

    def test_one_off_block_needs_both_datetimes(self):
        with self.assertRaises(ValidationError):
            UnavailableSlot(profile=self.master, is_recurring=False,
                            start_datetime=day_at(future_day(), '10:00')).clean()

    def test_one_off_block_end_must_be_after_start(self):
        start = day_at(future_day(), '10:00')
        with self.assertRaises(ValidationError):
            UnavailableSlot(profile=self.master, is_recurring=False,
                            start_datetime=start, end_datetime=start).clean()

    def test_valid_blocks_pass(self):
        from datetime import time
        start = day_at(future_day(), '10:00')
        UnavailableSlot(profile=self.master, is_recurring=False,
                        start_datetime=start, end_datetime=start + timedelta(hours=1)).clean()
        UnavailableSlot(profile=self.master, is_recurring=True, weekday=2,
                        start_time=time(12), end_time=time(13)).clean()
