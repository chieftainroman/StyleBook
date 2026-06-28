from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta, date as date_cls
from django.contrib.auth.decorators import login_required

from accounts.models import MasterProfile, Service
from .models import Booking
from .slots import get_available_slots, get_availability_summary
import json
import secrets
import string
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction

@login_required
def dashboard_view(request):
    """Master's dashboard."""
    return render(request, 'dashboard.html', {
        'active': 'dashboard',
    })

def book_master(request, username):
    """Public booking page for a master. Shows services + slot picker."""
    User = get_user_model()
    user = get_object_or_404(User, username=username)

    if not hasattr(user, 'profile'):
        raise Http404('Master not found')

    profile = user.profile

    if not profile.is_open_for_bookings():
        return render(request, 'bookings/not_available.html', {'master': user})

    services = profile.services.filter(is_active=True).order_by('sort_order', 'created_at')

    # Source tracking from URL param: /book/<username>/?src=qr
    source_param = request.GET.get('src', 'direct_link')
    if source_param not in [c[0] for c in Booking.SOURCE_CHOICES]:
        source_param = 'direct_link'

    context = {
        'master':   user,
        'profile':  profile,
        'services': services,
        'source':   source_param,
    }
    return render(request, 'bookings/book.html', context)


def availability_api(request, username):
    """
    JSON API: given ?service_id=X&date=YYYY-MM-DD return available slots.
    Used by the booking page's date/time picker.
    """
    User = get_user_model()
    user = get_object_or_404(User, username=username)
    profile = user.profile

    try:
        service_id = int(request.GET.get('service_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid service_id'}, status=400)

    try:
        service = profile.services.get(pk=service_id, is_active=True)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)

    date_str = request.GET.get('date', '')
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    # Don't allow booking past dates
    if target_date < timezone.now().date():
        return JsonResponse({'slots': []})

    # Don't allow more than 90 days out
    if (target_date - timezone.now().date()).days > 90:
        return JsonResponse({'slots': []})

    slots = get_available_slots(profile, service, target_date)

    return JsonResponse({
        'date':         target_date.isoformat(),
        'service_id':   service.id,
        'service_name': service.name,
        'duration':     service.duration_minutes,
        'slots':        [
            {
                'time':    s.strftime('%H:%M'),
                'display': s.strftime('%-I:%M %p'),  # Linux strftime
                'iso':     s.isoformat(),
            }
            for s in slots
        ],
    })


def availability_summary_api(request, username):
    """
    JSON API: given ?service_id=X return which dates in next 30 days have slots.
    Used by the date picker to highlight available dates.
    """
    User = get_user_model()
    user = get_object_or_404(User, username=username)
    profile = user.profile

    try:
        service_id = int(request.GET.get('service_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid service_id'}, status=400)

    try:
        service = profile.services.get(pk=service_id, is_active=True)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)

    summary = get_availability_summary(profile, service, num_days=30)

    return JsonResponse({
        'service_id': service.id,
        'availability': {d.isoformat(): bool(has) for d, has in summary.items()},
    })
    



def _generate_otp_code():
    """6-digit numeric code."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def _client_ip(request):
    """Best-effort client IP extraction."""
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _check_rate_limits(email, ip):
    """Return None if OK, or error message if rate-limited."""
    from .models import OTPRequest
    one_hour_ago = timezone.now() - timedelta(hours=1)

    by_email = OTPRequest.objects.filter(
        client_email__iexact=email,
        created_at__gte=one_hour_ago,
    ).count()
    if by_email >= 5:
        return 'Too many requests for this email. Try again in an hour.'

    if ip:
        by_ip = OTPRequest.objects.filter(
            client_ip=ip,
            created_at__gte=one_hour_ago,
        ).count()
        if by_ip >= 20:
            return 'Too many requests from this network. Try again later.'

    return None


def _send_otp_email(booking, code):
    """Send 6-digit OTP to client_email."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings

    ctx = {
        'booking': booking,
        'code': code,
        'master_name': booking.master.user.username,
        'site_name': 'StyleBook',
    }
    subject = f'Your verification code: {code}'
    text_body = render_to_string('emails/booking_otp.txt', ctx)
    html_body = render_to_string('emails/booking_otp.html', ctx)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[booking.client_email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


def _send_booking_confirmed_emails(booking):
    """Send confirmation to client + notification to master after OTP success."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings

    # ── Client confirmation ──
    ctx = {
        'booking': booking,
        'master_name': booking.master.user.username,
        'site_name': 'StyleBook',
    }
    subject = f'Booking confirmed — {booking.reference_code}'
    text_body = render_to_string('emails/booking_confirmed_client.txt', ctx)
    html_body = render_to_string('emails/booking_confirmed_client.html', ctx)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[booking.client_email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)  # don't fail the request if email fails

    # ── Master notification ──
    if booking.master.user.email:
        ctx['client_name'] = booking.client_name
        subject = f'New booking from {booking.client_name} — {booking.reference_code}'
        text_body = render_to_string('emails/booking_notification_master.txt', ctx)
        html_body = render_to_string('emails/booking_notification_master.html', ctx)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.master.user.email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)


@ensure_csrf_cookie
def book_master(request, username):
    """Public booking page for a master. Shows services + slot picker."""
    User = get_user_model()
    user = get_object_or_404(User, username=username)

    if not hasattr(user, 'profile'):
        raise Http404('Master not found')

    profile = user.profile

    if not profile.is_open_for_bookings():
        return render(request, 'bookings/not_available.html', {'master': user})

    services = profile.services.filter(is_active=True).order_by('sort_order', 'created_at')

    source_param = request.GET.get('src', 'direct_link')
    if source_param not in [c[0] for c in Booking.SOURCE_CHOICES]:
        source_param = 'direct_link'

    context = {
        'master':   user,
        'profile':  profile,
        'services': services,
        'source':   source_param,
    }
    return render(request, 'bookings/book.html', context)


def create_booking(request, username):
    """Create a pending booking from JSON payload + send OTP email."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    User = get_user_model()
    user = get_object_or_404(User, username=username)
    profile = user.profile

    if not profile.is_open_for_bookings():
        return JsonResponse({'error': 'Master not accepting bookings'}, status=400)

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Validate inputs
    try:
        service_id = int(data.get('service_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid service'}, status=400)

    try:
        service = profile.services.get(pk=service_id, is_active=True)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Service not available'}, status=404)

    slot_iso = data.get('slot_iso', '')
    try:
        start_time = datetime.fromisoformat(slot_iso)
        if timezone.is_naive(start_time) and timezone.is_aware(timezone.now()):
            start_time = timezone.make_aware(start_time)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid slot'}, status=400)

    client_name  = (data.get('client_name')  or '').strip()[:120]
    client_email = (data.get('client_email') or '').strip().lower()[:254]
    client_phone = (data.get('client_phone') or '').strip()[:30]
    client_notes = (data.get('client_notes') or '').strip()[:500]
    source       = data.get('source') or 'direct_link'

    if not client_name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    if not client_email or '@' not in client_email:
        return JsonResponse({'error': 'Valid email required'}, status=400)
    if source not in [c[0] for c in Booking.SOURCE_CHOICES]:
        source = 'direct_link'

    # Re-validate that the slot is STILL available (avoid race condition)
    available = get_available_slots(profile, service, start_time.date())
    naive_start = start_time.replace(tzinfo=None) if timezone.is_aware(start_time) else start_time
    available_naive = [
        (s.replace(tzinfo=None) if hasattr(s, 'tzinfo') and s.tzinfo else s)
        for s in available
    ]
    if naive_start not in available_naive:
        return JsonResponse({'error': 'That time slot is no longer available'}, status=409)

    # Rate limit OTP requests
    client_ip = _client_ip(request)
    rl = _check_rate_limits(client_email, client_ip)
    if rl:
        return JsonResponse({'error': rl}, status=429)

    # Check if this is a first-time client for this master
    has_prior = Booking.objects.filter(
        master=profile,
        client_email__iexact=client_email,
    ).exists()

    # Create the booking in 'pending_otp' state
    with transaction.atomic():
        booking = Booking.objects.create(
            master=profile,
            service=service,
            start_time=start_time,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            client_notes=client_notes,
            source=source,
            first_time_client=not has_prior,
            status=Booking.STATUS_PENDING_OTP,
        )

        # Create OTP
        from .models import OTPRequest
        code = _generate_otp_code()
        OTPRequest.objects.create(
            booking=booking,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10),
            client_email=client_email,
            client_ip=client_ip,
        )

    # Send OTP email (outside the transaction so DB doesn't roll back if email fails)
    try:
        _send_otp_email(booking, code)
    except Exception as e:
        # Still return success — they can request a resend
        pass

    return JsonResponse({
        'reference_code': booking.reference_code,
        'client_email':   booking.client_email,
    })


def verify_otp(request, username):
    """Verify the OTP. On success, mark booking confirmed + send confirmation emails."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    ref_code = (data.get('reference_code') or '').strip().upper()
    code     = (data.get('code') or '').strip()

    if not ref_code or not code:
        return JsonResponse({'error': 'Missing fields'}, status=400)

    try:
        booking = Booking.objects.get(reference_code=ref_code)
    except Booking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found'}, status=404)

    if booking.status != Booking.STATUS_PENDING_OTP:
        return JsonResponse({'error': 'This booking is already confirmed or cancelled'}, status=400)

    # Find the most recent OTP for this booking
    from .models import OTPRequest
    otp = booking.otp_requests.filter(verified_at__isnull=True).order_by('-created_at').first()
    if not otp:
        return JsonResponse({'error': 'No active code. Please resend.'}, status=400)

    if otp.is_locked():
        return JsonResponse({'error': 'Too many wrong attempts. Please resend.'}, status=429)

    if otp.is_expired():
        return JsonResponse({'error': 'Code expired. Please resend.'}, status=400)

    otp.attempts += 1
    if otp.code != code:
        otp.save(update_fields=['attempts'])
        remaining = 5 - otp.attempts
        if remaining <= 0:
            return JsonResponse({'error': 'Too many wrong attempts. Please resend.'}, status=429)
        return JsonResponse({'error': f'Wrong code. {remaining} attempts left.'}, status=400)

    # Success
    otp.verified_at = timezone.now()
    otp.save(update_fields=['verified_at', 'attempts'])

    booking.status = Booking.STATUS_CONFIRMED
    booking.save(update_fields=['status'])

    # Send confirmation emails
    try:
        _send_booking_confirmed_emails(booking)
    except Exception:
        pass

    return JsonResponse({
        'reference_code': booking.reference_code,
        'client_email':   booking.client_email,
        'status':         booking.status,
    })


def resend_otp(request, username):
    """Send a fresh OTP for an existing pending booking."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    ref_code = (data.get('reference_code') or '').strip().upper()
    try:
        booking = Booking.objects.get(reference_code=ref_code)
    except Booking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found'}, status=404)

    if booking.status != Booking.STATUS_PENDING_OTP:
        return JsonResponse({'error': 'Booking is no longer pending'}, status=400)

    client_ip = _client_ip(request)
    rl = _check_rate_limits(booking.client_email, client_ip)
    if rl:
        return JsonResponse({'error': rl}, status=429)

    from .models import OTPRequest
    code = _generate_otp_code()
    OTPRequest.objects.create(
        booking=booking,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=10),
        client_email=booking.client_email,
        client_ip=client_ip,
    )

    try:
        _send_otp_email(booking, code)
    except Exception:
        return JsonResponse({'error': 'Could not send email. Try again.'}, status=500)

    return JsonResponse({'ok': True})
    
    
    
@login_required
def reservations_view(request):
    """Master's reservations page — list view or calendar view."""
    profile = request.user.profile

    # View mode: list (default) or calendar
    view_mode = request.GET.get('view', 'list')
    if view_mode not in ('list', 'calendar'):
        view_mode = 'list'

    # Tab filter for list view
    tab = request.GET.get('tab', 'upcoming')
    if tab not in ('upcoming', 'past', 'cancelled', 'all'):
        tab = 'upcoming'

    now = timezone.now()
    bookings_qs = Booking.objects.filter(master=profile).select_related('service')

    # ── List view: tab-filtered bookings ──
    if tab == 'upcoming':
        bookings = bookings_qs.filter(
            start_time__gte=now,
            status__in=[Booking.STATUS_PENDING_OTP, Booking.STATUS_CONFIRMED],
        ).order_by('start_time')
    elif tab == 'past':
        bookings = bookings_qs.filter(
            start_time__lt=now,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW],
        ).order_by('-start_time')
    elif tab == 'cancelled':
        bookings = bookings_qs.filter(
            status__in=[Booking.STATUS_CANCELLED, Booking.STATUS_REFUSED],
        ).order_by('-start_time')
    else:
        bookings = bookings_qs.order_by('-start_time')

    counts = {
        'upcoming': bookings_qs.filter(
            start_time__gte=now,
            status__in=[Booking.STATUS_PENDING_OTP, Booking.STATUS_CONFIRMED],
        ).count(),
        'past': bookings_qs.filter(
            start_time__lt=now,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED, Booking.STATUS_NO_SHOW],
        ).count(),
        'cancelled': bookings_qs.filter(
            status__in=[Booking.STATUS_CANCELLED, Booking.STATUS_REFUSED],
        ).count(),
        'all': bookings_qs.count(),
    }

    # ── Calendar view: week window based on ?week=YYYY-MM-DD ──
    week_data = None
    if view_mode == 'calendar':
        week_start_str = request.GET.get('week', '')
        try:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            # Default to start of current week (Monday)
            today = now.date()
            week_start = today - timedelta(days=today.weekday())

        # Force to Monday of that week
        week_start = week_start - timedelta(days=week_start.weekday())
        week_end = week_start + timedelta(days=7)

        # Get all bookings in this week (any non-cancelled status)
        week_bookings = bookings_qs.filter(
            start_time__gte=week_start,
            start_time__lt=week_end,
            status__in=[
                Booking.STATUS_PENDING_OTP,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_COMPLETED,
                Booking.STATUS_NO_SHOW,
            ],
        ).order_by('start_time')

        # Build day-by-day structure
        days = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_bookings = [
                b for b in week_bookings
                if b.start_time.date() == day_date
            ]
            days.append({
                'date': day_date,
                'is_today': day_date == now.date(),
                'is_past': day_date < now.date(),
                'bookings': day_bookings,
            })

        week_data = {
            'start':      week_start,
            'end':        week_start + timedelta(days=6),
            'days':       days,
            'prev_week':  week_start - timedelta(days=7),
            'next_week':  week_start + timedelta(days=7),
            'this_week':  now.date() - timedelta(days=now.date().weekday()),
        }

    context = {
        'active':    'reservations',
        'view_mode': view_mode,
        'tab':       tab,
        'bookings':  bookings,
        'counts':    counts,
        'week_data': week_data,
    }
    return render(request, 'bookings/reservations.html', context)

@login_required
def booking_detail(request, ref):
    """Detail page for a single booking. Built fully in Step 5C."""
    booking = get_object_or_404(
        Booking,
        reference_code=ref,
        master=request.user.profile,
    )
    return render(request, 'bookings/booking_detail.html', {
        'booking': booking,
        'active': 'reservations',
    })