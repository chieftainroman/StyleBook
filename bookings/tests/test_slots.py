"""
Tests for bookings/slots.py — the availability engine.

This is the most important logic in the app: if it's wrong, clients book
times the master can't do, or can't book times the master is free.

Every test passes a fixed `now=` so results never depend on when the suite
runs. DAY is a Tuesday; NOW is the evening before, so lead time doesn't
interfere unless a test sets it on purpose.
"""
from datetime import date, datetime, time, timedelta

from django.test import TestCase

from accounts.models import UnavailableSlot
from bookings.models import Booking
from bookings.slots import get_availability_summary, get_available_slots
from core.factories import day_at, make_booking, make_master, make_service, open_every_day

DAY = date(2030, 1, 8)                    # a Tuesday
NOW = datetime(2030, 1, 7, 20, 0)         # Monday evening, the day before


def times(slots):
    """[datetime(…10:00), datetime(…10:15)] -> ['10:00', '10:15'] for readable asserts."""
    return [s.strftime('%H:%M') for s in slots]


class WorkingHoursTests(TestCase):
    def setUp(self):
        self.master = make_master()
        self.cut = make_service(self.master, minutes=30)

    def slots(self, service=None, day=DAY, now=NOW):
        return times(get_available_slots(self.master, service or self.cut, day, now=now))

    def test_open_day_offers_a_slot_every_15_minutes(self):
        slots = self.slots()
        self.assertEqual(slots[0], '09:00')
        self.assertEqual(slots[1], '09:15')
        # 09:00 → 17:30 inclusive, every 15 min = 35 starts
        self.assertEqual(len(slots), 35)

    def test_last_slot_lets_the_service_finish_by_closing(self):
        self.assertEqual(self.slots()[-1], '17:30')                       # 30 min → ends 18:00
        hour = make_service(self.master, 'Color', minutes=60)
        self.assertEqual(self.slots(hour)[-1], '17:00')                   # 60 min → ends 18:00

    def test_odd_durations_still_start_on_the_15_minute_grid(self):
        fifty = make_service(self.master, 'Odd', minutes=50)
        slots = self.slots(fifty)
        self.assertEqual(slots[-1], '17:00')                              # 17:15 + 50 = 18:05, too late
        self.assertTrue(all(s[-2:] in ('00', '15', '30', '45') for s in slots))

    def test_service_longer_than_the_open_hours_has_no_slots(self):
        self.master.working_hours = open_every_day('09:00', '10:00')
        self.master.save()
        long_one = make_service(self.master, 'Long', minutes=90)
        self.assertEqual(self.slots(long_one), [])

    def test_closed_day_has_no_slots(self):
        hours = open_every_day()
        hours['tue']['closed'] = True
        self.master.working_hours = hours
        self.master.save()
        self.assertEqual(self.slots(), [])

    def test_day_missing_from_working_hours_counts_as_closed(self):
        hours = open_every_day()
        del hours['tue']
        self.master.working_hours = hours
        self.master.save()
        self.assertEqual(self.slots(), [])

    def test_empty_working_hours_fall_back_to_the_default_week(self):
        self.master.working_hours = {}
        self.master.save()
        self.assertEqual(self.slots()[0], '09:00')                        # default Tue 09–18
        saturday = DAY + timedelta(days=4)
        self.assertEqual(self.slots(day=saturday), [])                    # default Sat closed

    def test_malformed_hours_give_no_slots_instead_of_crashing(self):
        for bad_open in ('abc', '', '9', '25:99'):
            with self.subTest(open=bad_open):
                hours = open_every_day()
                hours['tue']['open'] = bad_open
                self.master.working_hours = hours
                self.master.save()
                self.assertEqual(self.slots(), [])

    def test_close_before_open_gives_no_slots(self):
        self.master.working_hours = open_every_day('18:00', '09:00')
        self.master.save()
        self.assertEqual(self.slots(), [])

    def test_unpadded_times_are_accepted(self):
        self.master.working_hours = open_every_day('9:00', '18:00')
        self.master.save()
        self.assertEqual(self.slots()[0], '09:00')


class LeadTimeTests(TestCase):
    def setUp(self):
        self.master = make_master(lead_hours=2)
        self.cut = make_service(self.master, minutes=30)

    def test_slots_inside_the_lead_time_are_hidden(self):
        now = day_at(DAY, '10:05')
        slots = times(get_available_slots(self.master, self.cut, DAY, now=now))
        self.assertEqual(slots[0], '12:15')                               # first grid slot ≥ 12:05

    def test_slot_exactly_at_the_lead_time_boundary_is_offered(self):
        now = day_at(DAY, '10:00')
        slots = times(get_available_slots(self.master, self.cut, DAY, now=now))
        self.assertEqual(slots[0], '12:00')

    def test_zero_lead_time_still_hides_slots_already_in_the_past(self):
        self.master.min_lead_time_hours = 0
        self.master.save()
        now = day_at(DAY, '10:05')
        slots = times(get_available_slots(self.master, self.cut, DAY, now=now))
        self.assertEqual(slots[0], '10:15')

    def test_past_dates_have_no_slots(self):
        yesterday = DAY - timedelta(days=1)
        self.assertEqual(get_available_slots(self.master, self.cut, yesterday, now=day_at(DAY, '08:00')), [])

    def test_long_lead_time_can_push_into_the_next_day(self):
        self.master.min_lead_time_hours = 48
        self.master.save()
        now = day_at(DAY, '08:00')
        self.assertEqual(get_available_slots(self.master, self.cut, DAY + timedelta(days=1), now=now), [])
        self.assertNotEqual(get_available_slots(self.master, self.cut, DAY + timedelta(days=2), now=now), [])


class UnavailableBlockTests(TestCase):
    def setUp(self):
        self.master = make_master()
        self.cut = make_service(self.master, minutes=30)

    def slots(self):
        return times(get_available_slots(self.master, self.cut, DAY, now=NOW))

    def block(self, start, end):
        return UnavailableSlot.objects.create(
            profile=self.master, is_recurring=False, start_datetime=start, end_datetime=end,
        )

    def test_one_off_block_removes_every_overlapping_slot(self):
        self.block(day_at(DAY, '12:00'), day_at(DAY, '13:00'))
        slots = self.slots()
        self.assertIn('11:30', slots)            # 11:30–12:00 ends exactly as the block starts
        for gone in ('11:45', '12:00', '12:15', '12:30', '12:45'):
            self.assertNotIn(gone, slots)
        self.assertIn('13:00', slots)            # starts exactly as the block ends

    def test_block_spanning_several_days_closes_the_whole_day(self):
        self.block(day_at(DAY - timedelta(days=1), '18:00'), day_at(DAY + timedelta(days=1), '09:00'))
        self.assertEqual(self.slots(), [])

    def test_block_on_another_day_is_ignored(self):
        self.block(day_at(DAY + timedelta(days=1), '09:00'), day_at(DAY + timedelta(days=1), '18:00'))
        self.assertEqual(len(self.slots()), 35)

    def test_another_masters_block_is_ignored(self):
        other = make_master('other')
        UnavailableSlot.objects.create(profile=other, is_recurring=False,
                                       start_datetime=day_at(DAY, '09:00'), end_datetime=day_at(DAY, '18:00'))
        self.assertEqual(len(self.slots()), 35)

    def test_weekly_block_applies_on_its_weekday(self):
        UnavailableSlot.objects.create(profile=self.master, is_recurring=True, weekday=DAY.weekday(),
                                       start_time=time(13, 0), end_time=time(14, 0), reason='Lunch')
        slots = self.slots()
        self.assertNotIn('13:00', slots)
        self.assertNotIn('13:30', slots)
        self.assertIn('14:00', slots)

    def test_weekly_block_on_a_different_weekday_is_ignored(self):
        UnavailableSlot.objects.create(profile=self.master, is_recurring=True, weekday=(DAY.weekday() + 1) % 7,
                                       start_time=time(9, 0), end_time=time(18, 0))
        self.assertEqual(len(self.slots()), 35)


class ExistingBookingTests(TestCase):
    def setUp(self):
        self.master = make_master()
        self.cut = make_service(self.master, minutes=30)

    def slots(self):
        return times(get_available_slots(self.master, self.cut, DAY, now=NOW))

    def test_confirmed_booking_blocks_only_its_own_interval(self):
        make_booking(self.master, self.cut, day_at(DAY, '10:00'))
        slots = self.slots()
        self.assertIn('09:30', slots)            # ends 10:00 — back-to-back is fine
        self.assertNotIn('09:45', slots)
        self.assertNotIn('10:00', slots)
        self.assertNotIn('10:15', slots)
        self.assertIn('10:30', slots)            # starts as the booking ends

    def test_pending_otp_booking_also_holds_the_slot(self):
        make_booking(self.master, self.cut, day_at(DAY, '10:00'), status=Booking.STATUS_PENDING_OTP)
        self.assertNotIn('10:00', self.slots())

    def test_cancelled_and_refused_bookings_free_the_slot(self):
        make_booking(self.master, self.cut, day_at(DAY, '10:00'), status=Booking.STATUS_CANCELLED)
        make_booking(self.master, self.cut, day_at(DAY, '11:00'), status=Booking.STATUS_REFUSED)
        slots = self.slots()
        self.assertIn('10:00', slots)
        self.assertIn('11:00', slots)

    def test_a_long_booking_blocks_a_short_service_inside_it(self):
        color = make_service(self.master, 'Color', minutes=120)
        make_booking(self.master, color, day_at(DAY, '10:00'))           # 10:00–12:00
        slots = self.slots()
        for gone in ('10:00', '10:45', '11:30'):
            self.assertNotIn(gone, slots)
        self.assertIn('12:00', slots)

    def test_capacity_two_allows_a_second_client_but_not_a_third(self):
        self.master.concurrent_clients = 2
        self.master.save()
        make_booking(self.master, self.cut, day_at(DAY, '10:00'), email='a@example.com')
        self.assertIn('10:00', self.slots())
        make_booking(self.master, self.cut, day_at(DAY, '10:00'), email='b@example.com')
        self.assertNotIn('10:00', self.slots())

    def test_another_masters_bookings_do_not_block(self):
        other = make_master('other')
        other_cut = make_service(other)
        make_booking(other, other_cut, day_at(DAY, '10:00'))
        self.assertIn('10:00', self.slots())

    def test_booking_crossing_midnight_into_the_day_blocks_the_morning(self):
        self.master.working_hours = open_every_day('00:00', '23:45')
        self.master.save()
        late = make_service(self.master, 'Late', minutes=120)
        make_booking(self.master, late, day_at(DAY - timedelta(days=1), '23:00'))   # until 01:00 on DAY
        slots = self.slots()
        self.assertNotIn('00:30', slots)
        self.assertIn('01:00', slots)


class AvailabilitySummaryTests(TestCase):
    def setUp(self):
        hours = open_every_day()
        hours['sun']['closed'] = True
        self.master = make_master(hours=hours)
        self.cut = make_service(self.master, minutes=30)

    def test_summary_covers_the_requested_number_of_days(self):
        summary = get_availability_summary(self.master, self.cut, num_days=14, start_date=DAY, now=NOW)
        self.assertEqual(len(summary), 14)
        self.assertEqual(min(summary), DAY)

    def test_closed_days_are_false_and_open_days_true(self):
        summary = get_availability_summary(self.master, self.cut, num_days=7, start_date=DAY, now=NOW)
        sunday = DAY + timedelta(days=(6 - DAY.weekday()))
        self.assertFalse(summary[sunday])
        self.assertTrue(summary[DAY])

    def test_fully_booked_day_is_false(self):
        self.master.working_hours = open_every_day('09:00', '09:30')
        self.master.save()
        make_booking(self.master, self.cut, day_at(DAY, '09:00'))
        summary = get_availability_summary(self.master, self.cut, num_days=1, start_date=DAY, now=NOW)
        self.assertFalse(summary[DAY])
