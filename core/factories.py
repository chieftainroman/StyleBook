"""
Tiny helpers for building test data. Use them from any app's tests:

    from core.factories import make_master, make_service, make_booking, day_at, future_day

Every helper returns real saved model objects, so tests read like a story:

    master  = make_master('ana')
    haircut = make_service(master, minutes=30)
    booking = make_booking(master, haircut, day_at(future_day(), '10:00'))
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Service
from bookings.models import Booking, OTPRequest

DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def open_every_day(open_='09:00', close='18:00'):
    """Working hours with every day of the week open — keeps slot tests weekday-independent."""
    return {d: {'open': open_, 'close': close, 'closed': False} for d in DAYS}


def make_master(username='master', *, email=None, password='test-pass-123',
                capacity=1, lead_hours=0, hours=None, onboarded=True, **profile_fields):
    """
    A User + a fully set-up MasterProfile (the profile itself is created by
    accounts.signals when the User is saved). Returns the profile; the user
    is at `profile.user`.

    Defaults are chosen so tests are deterministic:
      * open 09:00–18:00 every day
      * lead time 0 (tests that care about lead time set it explicitly)
      * capacity 1
    """
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com' if email is None else email,
        password=password,
    )
    profile = user.profile
    profile.specialty = 'barber'
    profile.location = 'New York'
    profile.years_exp = 5
    profile.bio = 'Barber with five years behind the chair.'
    profile.phone = '+1 555 0100'
    profile.onboarding_completed = onboarded
    profile.concurrent_clients = capacity
    profile.min_lead_time_hours = lead_hours
    profile.working_hours = hours if hours is not None else open_every_day()
    for field, value in profile_fields.items():
        setattr(profile, field, value)
    profile.save()
    return profile


def make_service(profile, name='Haircut', minutes=30, price='40.00', active=True, **fields):
    return Service.objects.create(
        profile=profile, name=name, duration_minutes=minutes,
        price=Decimal(price), is_active=active, **fields,
    )


def future_day(days=7):
    """A date `days` from today — far enough ahead that lead time never interferes."""
    return timezone.now().date() + timedelta(days=days)


def day_at(day, hhmm):
    """day_at(date(2030, 1, 8), '10:30') -> datetime(2030, 1, 8, 10, 30)."""
    hours, minutes = (int(x) for x in hhmm.split(':'))
    return datetime.combine(day, time(hours, minutes))


def make_booking(profile, service, start, *, status=Booking.STATUS_CONFIRMED,
                 name='Client Person', email='client@example.com', **fields):
    return Booking.objects.create(
        master=profile, service=service, start_time=start,
        client_name=name, client_email=email, status=status, **fields,
    )


def make_otp(booking, code='123456', *, minutes_valid=10, ip='203.0.113.5', **fields):
    return OTPRequest.objects.create(
        booking=booking, code=code,
        expires_at=timezone.now() + timedelta(minutes=minutes_valid),
        client_email=booking.client_email, client_ip=ip, **fields,
    )
