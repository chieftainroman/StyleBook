import os
from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
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

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

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
        if not specialty:
            return redirect('onboarding')

        messages.success(request, 'Welcome to StyleBook!')
        return redirect('dashboard')

    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('login')


#re_46RiEDbW_LrVQTC8cPCVJhzLeMbEZNg8W

# ═════════════════════════════════════════════════════
# Onboarding wizard
# ═════════════════════════════════════════════════════

# Step config: (step_number, name, mandatory, partial_template)
ONBOARDING_STEPS = [
    (1, 'Basic info',  True,  'onboarding/_step_basic.html'),
    (2, 'Photos',      False, 'onboarding/_step_photos.html'),
    (3, 'Bio',         True,  'onboarding/_step_bio.html'),
    (4, 'Achievements',False, 'onboarding/_step_achievements.html'),
    (5, 'Contact',     True,  'onboarding/_step_contact.html'),
]


def _step_meta(step_number):
    """Return the tuple for a given step number, or None."""
    for s in ONBOARDING_STEPS:
        if s[0] == step_number:
            return s
    return None


@login_required
def onboarding_start(request):
    """Render a wizard step. Step number comes from ?step=N (defaults to 1)."""
    # If already onboarded, kick them to dashboard
    if request.user.profile.onboarding_completed:
        return redirect('dashboard')

    # Parse and validate step
    try:
        step = int(request.GET.get('step', 1))
    except (ValueError, TypeError):
        step = 1
    if step < 1 or step > len(ONBOARDING_STEPS):
        step = 1

    meta = _step_meta(step)

    days = [
            ('mon', 'Monday'),
            ('tue', 'Tuesday'),
            ('wed', 'Wednesday'),
            ('thu', 'Thursday'),
            ('fri', 'Friday'),
            ('sat', 'Saturday'),
            ('sun', 'Sunday'),
        ]

    context = {
        'profile':        request.user.profile,
        'step':           step,
        'step_name':      meta[1],
        'step_mandatory': meta[2],
        'partial':        meta[3],
        'steps':          ONBOARDING_STEPS,
        'total_steps':    len(ONBOARDING_STEPS),
        'progress_pct':   int((step / len(ONBOARDING_STEPS)) * 100),
        'has_prev':       step > 1,
        'has_next':       step < len(ONBOARDING_STEPS),
        'is_last':        step == len(ONBOARDING_STEPS),
        'days':           days,
        'working_hours':  request.user.profile.get_working_hours(),
    }
    return render(request, 'onboarding/wizard.html', context)


@login_required
@require_POST
def onboarding_step_save(request, step):
    """
    Handle form POST from a wizard step. Save the data, then advance to next step
    (or finish if last step).
    """
    profile = request.user.profile

    # If already onboarded, abandon
    if profile.onboarding_completed:
        return redirect('dashboard')

    # Dispatch based on step number
    if step == 1:
        err = _save_step_basic(profile, request.POST)
    elif step == 3:
        err = _save_step_bio(profile, request.POST)
    elif step == 5:
        err = _save_step_contact(profile, request.POST)
    else:
        # Optional steps (2, 4) don't have a "save" — they're skip/next only
        err = None

    if err:
        messages.error(request, err)
        return redirect(f"{reverse('onboarding_start')}?step={step}")

    # Advance: if last step, mark as finished; otherwise go to next step
    if step >= 5:
        return redirect('onboarding_finish')
    return redirect(f"{reverse('onboarding_start')}?step={step + 1}")


# ── Per-step save helpers ───────────────────────────

def _save_step_basic(profile, post_data):
    """Step 1: specialty, location, years_exp. All required."""
    specialty = post_data.get('specialty', '').strip()
    location  = post_data.get('location', '').strip()
    try:
        years_exp = int(post_data.get('years_exp', 0))
    except (ValueError, TypeError):
        years_exp = 0

    if not specialty:
        return 'Please select your specialty.'
    if not location:
        return 'Please enter your location.'
    if years_exp <= 0:
        return 'Years of experience must be at least 1.'

    profile.specialty = specialty
    profile.location  = location
    profile.years_exp = years_exp
    profile.save(update_fields=['specialty', 'location', 'years_exp'])
    return None


def _save_step_bio(profile, post_data):
    """Step 3: bio. Required."""
    bio = post_data.get('bio', '').strip()
    if len(bio) < 20:
        return 'Please write a bio of at least 20 characters.'
    profile.bio = bio
    profile.save(update_fields=['bio'])
    return None


def _save_step_contact(profile, post_data):
    """Step 5: phone (required), ig_handle (optional), working hours (optional)."""
    phone     = post_data.get('phone', '').strip()
    ig_handle = post_data.get('ig_handle', '').strip().lstrip('@')

    if not phone:
        return 'Phone number is required.'

    # Parse working hours from per-day grid
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    hours = {}
    for d in days:
        closed = post_data.get(f'{d}_closed') == 'on'
        hours[d] = {
            'open':   post_data.get(f'{d}_open', '09:00'),
            'close':  post_data.get(f'{d}_close', '18:00'),
            'closed': closed,
        }

    profile.phone         = phone
    profile.ig_handle     = ig_handle
    profile.working_hours = hours
    profile.save(update_fields=['phone', 'ig_handle', 'working_hours'])
    return None


@login_required
def onboarding_finish(request):
    """Mark the user as onboarded and send them to the dashboard."""
    profile = request.user.profile
    profile.onboarding_completed = True
    profile.save(update_fields=['onboarding_completed'])
    messages.success(request, 'Welcome to StyleBook! You can edit your profile anytime.')
    return redirect('dashboard')


# Keep onboarding_skip as an alias for backward compatibility with the URL we wired earlier.
onboarding_skip = onboarding_finish


from .tokens import email_verification_token, decode_uid


def verify_email(request, uidb64, token):
    """Land here when user clicks the verification link in their email."""
    User = get_user_model()
    uid = decode_uid(uidb64)
    if uid is None:
        return render(request, 'accounts/verify_result.html', {'success': False})

    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        return render(request, 'accounts/verify_result.html', {'success': False})

    if not email_verification_token.check_token(user, token):
        return render(request, 'accounts/verify_result.html', {'success': False})

    # Valid — mark verified
    if hasattr(user, 'profile'):
        user.profile.email_verified = True
        user.profile.save(update_fields=['email_verified'])

    return render(request, 'accounts/verify_result.html', {'success': True})


@login_required
def resend_verification(request):
    """Resend verification email to the logged-in user."""
    from .emails import send_verification_email

    if request.user.profile.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('dashboard')

    send_verification_email(request, request.user)
    messages.success(request, f'Verification email sent to {request.user.email}. Check your inbox.')
    return redirect('dashboard')


from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password


def forgot_password(request):
    """User enters their email to receive a reset link."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter your email.')
            return redirect('forgot_password')

        User = get_user_model()
        users = User.objects.filter(email__iexact=email)
        # Always show the same success message regardless of whether the email exists
        # — prevents attackers from probing which emails are registered.
        if users.exists():
            from .emails import send_password_reset_email
            for user in users:
                send_password_reset_email(request, user)

        messages.success(request, f'If an account exists for {email}, a reset link has been sent.')
        return redirect('login')

    return render(request, 'accounts/forgot_password.html')


def reset_password(request, uidb64, token):
    """User clicks the link in the reset email, lands here to set a new password."""
    User = get_user_model()
    uid = decode_uid(uidb64)
    if uid is None:
        return render(request, 'accounts/reset_invalid.html')

    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        return render(request, 'accounts/reset_invalid.html')

    if not default_token_generator.check_token(user, token):
        return render(request, 'accounts/reset_invalid.html')

    if request.method == 'POST':
        new_password  = request.POST.get('new_password', '')
        new_password2 = request.POST.get('new_password2', '')

        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        elif new_password != new_password2:
            messages.error(request, 'Passwords do not match.')
        else:
            user.password = make_password(new_password)
            user.save(update_fields=['password'])
            messages.success(request, 'Password updated. You can now log in.')
            return redirect('login')

    return render(request, 'accounts/reset_password.html', {'uidb64': uidb64, 'token': token})