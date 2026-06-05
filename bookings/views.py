from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse

from .models import Reservation
from portfolio.models import PortfolioItem


@login_required
def dashboard(request):
    today_str       = date.today().strftime('%Y-%m-%d')
    first_of_month  = date.today().replace(day=1).strftime('%Y-%m-%d')

    today_reservations = Reservation.objects.filter(
        user=request.user,
        date=today_str
    ).order_by('time')

    month_count = Reservation.objects.filter(
        user=request.user,
        date__gte=first_of_month
    ).count()

    completed_count = Reservation.objects.filter(
        user=request.user,
        status='completed'
    ).count()

    portfolio_count = PortfolioItem.objects.filter(
        user=request.user
    ).count()

    all_clients  = Reservation.objects.filter(user=request.user).values_list('client_name', flat=True)
    client_names = [c.lower().strip() for c in all_clients]
    unique_clients = set(client_names)

    if unique_clients:
        repeat_clients = sum(1 for c in unique_clients if client_names.count(c) > 1)
        return_rate    = int((repeat_clients / len(unique_clients)) * 100)
    else:
        return_rate = 0

    recent_portfolio = PortfolioItem.objects.filter(
        user=request.user
    ).order_by('-id')[:4]

    return render(request, 'dashboard.html', {
        'active':             'dashboard',
        'today_reservations': today_reservations,
        'month_count':        month_count,
        'completed_count':    completed_count,
        'portfolio_count':    portfolio_count,
        'return_rate':        return_rate,
        'recent_portfolio':   recent_portfolio,
    })


@login_required
def reservations_view(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name', '').strip()
        res_date    = request.POST.get('date', '')
        res_time    = request.POST.get('time', '')
        service     = request.POST.get('service', '').strip()
        notes       = request.POST.get('notes', '').strip()

        if not client_name or not res_date or not res_time or not service:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('reservations')

        Reservation.objects.create(
            user=request.user,
            client_name=client_name,
            date=res_date,
            time=res_time,
            service=service,
            notes=notes,
            status='upcoming',
        )

        messages.success(request, 'Booking saved!')
        return redirect('reservations')

    today_str = date.today().strftime('%Y-%m-%d')

    upcoming = Reservation.objects.filter(
        user=request.user,
        status='upcoming',
        date__gte=today_str
    ).order_by('date', 'time')

    completed = Reservation.objects.filter(
        user=request.user,
        status='completed'
    ).order_by('-date', '-time')

    all_reservations = Reservation.objects.filter(
        user=request.user
    ).order_by('-date', '-time')

    return render(request, 'reservations.html', {
        'active':           'reservations',
        'upcoming':         upcoming,
        'completed':        completed,
        'all_reservations': all_reservations,
    })


@login_required
def complete_reservation(request, res_id):
    reservation = get_object_or_404(Reservation, id=res_id)

    if reservation.user != request.user:
        messages.error(request, 'Not authorized.')
        return redirect('reservations')

    reservation.status = 'completed'
    reservation.save()

    messages.success(request, f'{reservation.client_name} marked as done!')
    return redirect('reservations')


@login_required
def delete_reservation(request, res_id):
    reservation = get_object_or_404(Reservation, id=res_id)

    if reservation.user != request.user:
        messages.error(request, 'Not authorized.')
        return redirect('reservations')

    reservation.delete()
    messages.success(request, 'Booking deleted.')
    return redirect('reservations')