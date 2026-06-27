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
    Return available slot start times for `service` with `master` on `target_date`.
    Works with USE_TZ=True or False.
    """
    if now is None:
        now = timezone.now()

    use_tz = timezone.is_aware(now)
    now_naive = timezone.make_naive(now) if use_tz else now

    # ── 1. Working hours for this weekday ──
    weekday_idx = target_date.weekday()
    weekday_key = WEEKDAY_KEYS[weekday_idx]
    day_hours = master.get_working_hours().get(weekday_key, {})

    if day_hours.get('closed', True):
        return []

    try:
        open_t  = _parse_time(day_hours.get('open', '09:00'))
        close_t = _parse_time(day_hours.get('close', '18:00'))
    except (ValueError, AttributeError):
        return []

    day_open  = datetime.combine(target_date, open_t)
    day_close = datetime.combine(target_date, close_t)

    # ── 2. Candidate slots (all naive) ──
    service_duration = timedelta(minutes=service.duration_minutes)
    slot_step        = timedelta(minutes=SLOT_STEP_MINUTES)
    earliest_allowed = now_naive + timedelta(hours=master.min_lead_time_hours)

    candidates = []
    current = day_open
    while current + service_duration <= day_close:
        if current >= earliest_allowed:
            candidates.append(current)
        current += slot_step

    if not candidates:
        return []

    # ── 3. Single-occurrence unavailable slots ──
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end   = day_start + timedelta(days=1)

    single_unavailable = master.unavailable_slots.filter(
        is_recurring=False,
        start_datetime__lt=day_end,
        end_datetime__gt=day_start,
    )

    blocked_ranges = []
    for u in single_unavailable:
        s = u.start_datetime
        e = u.end_datetime
        if timezone.is_aware(s):
            s = timezone.make_naive(s)
        if timezone.is_aware(e):
            e = timezone.make_naive(e)
        blocked_ranges.append((s, e))

    # ── 4. Recurring weekly blocks ──
    recurring_unavailable = master.unavailable_slots.filter(
        is_recurring=True,
        weekday=weekday_idx,
    )
    for u in recurring_unavailable:
        bs = datetime.combine(target_date, u.start_time)
        be = datetime.combine(target_date, u.end_time)
        blocked_ranges.append((bs, be))

    # ── 5. Existing bookings ──
    existing_bookings_raw = Booking.objects.filter(
        master=master,
        status__in=[Booking.STATUS_PENDING_OTP, Booking.STATUS_CONFIRMED],
        start_time__lt=day_end,
        end_time__gt=day_start,
    )
    existing_bookings = []
    for b in existing_bookings_raw:
        bs = b.start_time
        be = b.end_time
        if timezone.is_aware(bs):
            bs = timezone.make_naive(bs)
        if timezone.is_aware(be):
            be = timezone.make_naive(be)
        existing_bookings.append((bs, be))

    # ── 6. Filter candidates ──
    available = []
    capacity = master.concurrent_clients

    for slot_start in candidates:
        slot_end = slot_start + service_duration

        if _overlaps_any(slot_start, slot_end, blocked_ranges):
            continue

        overlapping = sum(
            1 for bs, be in existing_bookings
            if _intervals_overlap(slot_start, slot_end, bs, be)
        )
        if overlapping >= capacity:
            continue

        if use_tz:
            available.append(timezone.make_aware(slot_start, timezone.get_current_timezone()))
        else:
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