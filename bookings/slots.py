"""
Slot generation: given a master + service + date, return available slot times.

Algorithm:
1. Get the master's working hours for that weekday.
2. Compute the candidate slot times within those hours.
3. Subtract any single-occurrence unavailable_slots that overlap that day.
4. Subtract any recurring unavailable_slots that match the day's weekday.
5. Subtract any existing confirmed bookings, considering concurrent_clients capacity.
6. Filter out slots that violate the master's min_lead_time_hours.
7. Return remaining slots.
"""

from datetime import datetime, timedelta, date as date_cls
from django.utils import timezone
from .models import Booking


# Slot granularity: we offer slots every 15 minutes within working hours.
# Each booking blocks its exact service duration; this granularity controls
# WHERE slots can start, not how long they last.
SLOT_STEP_MINUTES = 15


# Day-of-week mapping: MasterProfile.working_hours uses 'mon','tue',...
# while Python's datetime.weekday() returns 0..6 (Mon..Sun).
WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def get_available_slots(master, service, target_date, now=None):
    """
    Return a list of datetime objects representing available start times
    for `service` with `master` on `target_date`.

    `target_date` is a date object (no time).
    `now` is optional — defaults to current time, used for lead-time filtering.
    """
    if now is None:
        now = timezone.now()

    # ── 1. Get working hours for this weekday ──
    weekday_idx = target_date.weekday()  # 0=Mon..6=Sun
    weekday_key = WEEKDAY_KEYS[weekday_idx]

    working_hours = master.get_working_hours()
    day_hours = working_hours.get(weekday_key, {})

    if day_hours.get('closed', True):
        return []

    open_str  = day_hours.get('open',  '09:00')
    close_str = day_hours.get('close', '18:00')

    try:
        open_t  = _parse_time(open_str)
        close_t = _parse_time(close_str)
    except ValueError:
        return []

    # Combine target_date with open/close times to get full datetimes (naive)
    naive_open  = datetime.combine(target_date, open_t)
    naive_close = datetime.combine(target_date, close_t)

    # Make them timezone-aware
    tz = timezone.get_current_timezone()
    day_open  = timezone.make_aware(naive_open, tz)
    day_close = timezone.make_aware(naive_close, tz)

    # ── 2. Build candidate slot start times ──
    service_duration = timedelta(minutes=service.duration_minutes)
    slot_step        = timedelta(minutes=SLOT_STEP_MINUTES)
    earliest_allowed = now + timedelta(hours=master.min_lead_time_hours)

    candidates = []
    current = day_open
    while current + service_duration <= day_close:
        # Must respect lead time
        if current >= earliest_allowed:
            candidates.append(current)
        current += slot_step

    if not candidates:
        return []

    # ── 3. Subtract single-occurrence unavailable slots ──
    day_start_utc = timezone.make_aware(
        datetime.combine(target_date, datetime.min.time()), tz
    )
    day_end_utc   = day_start_utc + timedelta(days=1)

    single_unavailable = master.unavailable_slots.filter(
        is_recurring=False,
        start_datetime__lt=day_end_utc,
        end_datetime__gt=day_start_utc,
    )

    blocked_ranges = [(u.start_datetime, u.end_datetime) for u in single_unavailable]

    # ── 4. Subtract recurring unavailable slots matching this weekday ──
    recurring_unavailable = master.unavailable_slots.filter(
        is_recurring=True,
        weekday=weekday_idx,
    )

    for u in recurring_unavailable:
        block_start_naive = datetime.combine(target_date, u.start_time)
        block_end_naive   = datetime.combine(target_date, u.end_time)
        block_start = timezone.make_aware(block_start_naive, tz)
        block_end   = timezone.make_aware(block_end_naive, tz)
        blocked_ranges.append((block_start, block_end))

    # ── 5. Subtract existing confirmed bookings (with concurrent_clients capacity) ──
    existing_bookings = Booking.objects.filter(
        master=master,
        status__in=[Booking.STATUS_PENDING_OTP, Booking.STATUS_CONFIRMED],
        start_time__lt=day_end_utc,
        end_time__gt=day_start_utc,
    )

    # ── 6. Filter candidates ──
    available = []
    capacity = master.concurrent_clients

    for slot_start in candidates:
        slot_end = slot_start + service_duration

        # Skip if overlaps any blocked range
        if _overlaps_any(slot_start, slot_end, blocked_ranges):
            continue

        # Count overlapping bookings — must respect capacity
        overlapping_count = sum(
            1 for b in existing_bookings
            if _intervals_overlap(slot_start, slot_end, b.start_time, b.end_time)
        )
        if overlapping_count >= capacity:
            continue

        available.append(slot_start)

    return available


# ─── Helpers ─────────────────────────────────────────────

def _parse_time(s):
    """Parse 'HH:MM' string into a datetime.time."""
    hh, mm = s.split(':')
    return datetime.strptime(f'{int(hh):02d}:{int(mm):02d}', '%H:%M').time()


def _intervals_overlap(a_start, a_end, b_start, b_end):
    """True if [a_start, a_end) overlaps [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def _overlaps_any(start, end, ranges):
    return any(_intervals_overlap(start, end, rs, re) for rs, re in ranges)


# ─── Higher-level: get next N days with availability ──────

def get_availability_summary(master, service, num_days=14, start_date=None, now=None):
    """
    Return a dict like:
      {
        date(2026, 7, 1): True,   # has slots
        date(2026, 7, 2): False,  # no slots (closed/blocked/booked solid)
        ...
      }
    Used by the booking page to show which days are bookable.
    """
    if now is None:
        now = timezone.now()
    if start_date is None:
        start_date = now.date()

    summary = {}
    for offset in range(num_days):
        d = start_date + timedelta(days=offset)
        slots = get_available_slots(master, service, d, now=now)
        summary[d] = len(slots) > 0
    return summary