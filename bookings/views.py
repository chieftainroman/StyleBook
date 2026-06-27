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