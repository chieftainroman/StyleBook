"""One-off slot generator test. Delete after running."""
from accounts.models import MasterProfile, Service, UnavailableSlot
from bookings.models import Booking
from bookings.slots import get_available_slots
from django.utils import timezone
from datetime import timedelta, datetime


def naive(d):
    if hasattr(d, 'tzinfo') and d.tzinfo:
        return d.replace(tzinfo=None)
    return d


profile = MasterProfile.objects.get(user__username='chieftainroman')
service = profile.services.filter(is_active=True).first()
print('=' * 50)
print('Master:', profile.user.username)
print('Service:', service.name, service.duration_minutes, 'min')
print('Lead time:', profile.min_lead_time_hours, 'h')
print('Capacity:', profile.concurrent_clients)
print('=' * 50)

Booking.objects.filter(client_email__startswith='test').delete()
Booking.objects.filter(client_email__startswith='c').delete()
UnavailableSlot.objects.filter(reason__startswith='Test').delete()

print('\n-- Test 1: Booking creation --')
b = Booking.objects.create(
    master=profile, service=service,
    start_time=timezone.now() + timedelta(days=2, hours=3),
    client_name='Test', client_email='test1@example.com',
    status=Booking.STATUS_CONFIRMED,
)
print('  Reference:', b.reference_code)
print('  End time:', b.end_time)
b.delete()

print('\n-- Test 2: Slots across 7 days --')
for offset in range(7):
    d = (timezone.now() + timedelta(days=offset)).date()
    slots = get_available_slots(profile, service, d)
    print('  ', d, d.strftime('%A'), ':', len(slots), 'slots')

test_date = None
for offset in range(1, 14):
    d = (timezone.now() + timedelta(days=offset)).date()
    if len(get_available_slots(profile, service, d)) > 0:
        test_date = d
        break
print('  Using', test_date, 'for further tests')
baseline = len(get_available_slots(profile, service, test_date))
print('  Baseline:', baseline)

print('\n-- Test 3: Lead time --')
orig = profile.min_lead_time_hours
profile.min_lead_time_hours = 72
profile.save()
today = get_available_slots(profile, service, timezone.now().date())
print('  Today with 72h lead:', len(today), '(expect 0)')
profile.min_lead_time_hours = orig
profile.save()

print('\n-- Test 4: Capacity --')
profile.concurrent_clients = 2
profile.save()
noon = datetime.combine(test_date, datetime.strptime('12:00', '%H:%M').time())
b1 = Booking.objects.create(
    master=profile, service=service, start_time=noon,
    client_name='C1', client_email='c1@example.com',
    status=Booking.STATUS_CONFIRMED,
)
after_1 = len(get_available_slots(profile, service, test_date))
print('  1 booking, cap 2:', after_1)
b2 = Booking.objects.create(
    master=profile, service=service, start_time=noon,
    client_name='C2', client_email='c2@example.com',
    status=Booking.STATUS_CONFIRMED,
)
after_2 = len(get_available_slots(profile, service, test_date))
print('  2 bookings, cap 2:', after_2, 'diff:', after_1 - after_2)
b1.delete()
b2.delete()
profile.concurrent_clients = 1
profile.save()

print('\n-- Test 5: Single block --')
bs = datetime.combine(test_date, datetime.strptime('14:00', '%H:%M').time())
be = datetime.combine(test_date, datetime.strptime('16:00', '%H:%M').time())
u = UnavailableSlot.objects.create(
    profile=profile, is_recurring=False,
    start_datetime=bs, end_datetime=be, reason='Test block',
)
slots = get_available_slots(profile, service, test_date)
inside = sum(1 for s in slots if bs <= naive(s) < be)
print('  Slots inside 14-16:', inside, '(expect 0)')
u.delete()

print('\n-- Test 6: Recurring block --')
u = UnavailableSlot.objects.create(
    profile=profile, is_recurring=True,
    weekday=test_date.weekday(),
    start_time=datetime.strptime('12:00', '%H:%M').time(),
    end_time=datetime.strptime('13:00', '%H:%M').time(),
    reason='Test lunch',
)
slots = get_available_slots(profile, service, test_date)
ls = datetime.combine(test_date, datetime.strptime('12:00', '%H:%M').time())
le = datetime.combine(test_date, datetime.strptime('13:00', '%H:%M').time())
inside = sum(1 for s in slots if ls <= naive(s) < le)
print('  Slots inside recurring 12-13:', inside, '(expect 0)')
u.delete()

print('\n-- Test 7: Cleanup --')
Booking.objects.filter(client_email__startswith='test').delete()
Booking.objects.filter(client_email__startswith='c').delete()
UnavailableSlot.objects.filter(reason__startswith='Test').delete()

print('\n' + '=' * 50)
print('DONE')
print('=' * 50)