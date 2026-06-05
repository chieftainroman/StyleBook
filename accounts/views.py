import os
from datetime import date

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import MasterProfile

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if not user:
            messages.error(request, 'Invalid username or password.')
            return redirect('login')

        login(request, user)

        # Check if profile is complete
        profile, _ = MasterProfile.objects.get_or_create(user=user)
        if not profile.specialty:
            return redirect('onboarding')

        next_page = request.GET.get('next')
        return redirect(next_page or 'dashboard')

    return render(request, 'login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        password  = request.POST.get('password', '')
        specialty = request.POST.get('specialty', '')
        location  = request.POST.get('location', '').strip()
        years_exp = request.POST.get('years_exp', '0').strip()
        ig_handle = request.POST.get('ig_handle', '').strip()
        bio       = request.POST.get('bio', '').strip()

        if not username or not email or not password:
            messages.error(request, 'All fields are required.')
            return redirect('register')

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        try:
            years = int(years_exp)
        except ValueError:
            years = 0

        # ── FIX: use get_or_create, signal already made the profile ──
        profile, _ = MasterProfile.objects.get_or_create(user=user)
        profile.specialty = specialty
        profile.location  = location
        profile.years_exp = years
        profile.ig_handle = ig_handle
        profile.bio       = bio
        profile.save()

        login(request, user)

        # If they skipped specialty in step 2 send to onboarding
        if not specialty:
            return redirect('onboarding')

        messages.success(request, 'Welcome to StyleBook!')
        return redirect('dashboard')

    return render(request, 'register.html')
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        password  = request.POST.get('password', '')
        specialty = request.POST.get('specialty', '')
        location  = request.POST.get('location', '').strip()
        years_exp = request.POST.get('years_exp', '0').strip()
        ig_handle = request.POST.get('ig_handle', '').strip()
        bio       = request.POST.get('bio', '').strip()

        if not username or not email or not password:
            messages.error(request, 'All fields are required.')
            return redirect('register')

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        try:
            years = int(years_exp)
        except ValueError:
            years = 0

        MasterProfile.objects.create(
            user=user,
            specialty=specialty,
            location=location,
            years_exp=years,
            ig_handle=ig_handle,
            bio=bio,
        )

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        # If they skipped specialty in step 2 send to onboarding
        if not specialty:
            return redirect('onboarding')

        messages.success(request, 'Welcome to StyleBook!')
        return redirect('dashboard')

    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('login')


@login_required
def onboarding_view(request):
    profile, _ = MasterProfile.objects.get_or_create(user=request.user)

    if profile.specialty:
        return redirect('dashboard')

    if request.method == 'POST':
        # If skipped just go to dashboard
        if request.POST.get('skip'):
            return redirect('dashboard')

        profile.specialty = request.POST.get('specialty', '').strip()
        profile.location  = request.POST.get('location', '').strip()
        profile.ig_handle = request.POST.get('ig_handle', '').strip()
        profile.bio       = request.POST.get('bio', '').strip()

        years = request.POST.get('years_exp', '0')
        try:
            profile.years_exp = int(years)
        except ValueError:
            profile.years_exp = 0

        profile.save()
        messages.success(request, 'Welcome to StyleBook!')
        return redirect('dashboard')

    return render(request, 'onboarding.html')