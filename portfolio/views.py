import os
import json
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings

from .models import PortfolioItem
from .utils import generate_instagram_image           # Pillow fallback
from . import placid                                   # NEW: Placid client
from bookings.models import Reservation
from accounts.models import MasterProfile


@login_required
def portfolio_view(request):
    portfolio_items = PortfolioItem.objects.filter(
        user=request.user
    ).order_by('-id')

    return render(request, 'portfolio.html', {
        'active':          'portfolio',
        'portfolio_items': portfolio_items,
    })



@login_required
def instagram_view(request):
    """
    GET: render the form.
    POST is rejected — it's handled by instagram_generate instead.
    """
    if request.method == 'POST':
        return redirect('instagram')

    prefill_service = ''
    prefill_client  = ''
    reservation_id  = request.GET.get('reservation_id')

    if reservation_id:
        res = Reservation.objects.filter(
            id=int(reservation_id),
            user=request.user
        ).first()
        if res:
            prefill_service = res.service
            prefill_client  = res.client_name

    profile, _ = MasterProfile.objects.get_or_create(user=request.user)

    return render(request, 'instagram.html', {
        'active':          'instagram',
        'generated':       None,
        'prefill_service': prefill_service,
        'prefill_client':  prefill_client,
        'reservation_id':  reservation_id,
        'profile':         profile,
        'templates_json':  json.dumps(placid.TEMPLATES),
    })


@login_required
def my_profile(request):
    return redirect('profile', username=request.user.username)


def profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    is_own_profile = request.user.is_authenticated and request.user.id == profile_user.id

    portfolio_items = PortfolioItem.objects.filter(
        user=profile_user
    ).order_by('-id')

    portfolio_count = portfolio_items.count()

    all_reservations = Reservation.objects.filter(user=profile_user)
    client_names     = set(r.client_name.lower().strip() for r in all_reservations)
    client_count     = len(client_names)

    profile, _ = MasterProfile.objects.get_or_create(user=profile_user)
    experience_items = []
    if profile.specialty and profile.years_exp:
        experience_items.append({
            'title':  f'{profile.specialty} — Independent',
            'period': f'{profile.years_exp} years experience',
        })
    if profile.location:
        experience_items.append({
            'title':  f'Based in {profile.location}',
            'period': f'Member since {profile_user.date_joined.strftime("%B %Y")}',
        })

    return render(request, 'profile.html', {
        'active':           'profile',
        'profile_user':     profile_user,
        'is_own_profile':   is_own_profile,
        'portfolio_items':  portfolio_items[:6],
        'portfolio_count':  portfolio_count,
        'client_count':     client_count,
        'experience_items': experience_items,
    })


@login_required
def edit_profile(request):
    if request.method == 'POST':
        profile = request.user.profile

        profile.specialty = request.POST.get('specialty', '').strip()
        profile.bio       = request.POST.get('bio', '').strip()
        profile.skills    = request.POST.get('skills', '').strip()
        profile.ig_handle = request.POST.get('ig_handle', '').strip()
        profile.location  = request.POST.get('location', '').strip()

        years = request.POST.get('years_exp', '0')
        try:
            profile.years_exp = int(years)
        except ValueError:
            profile.years_exp = 0

        profile.save()
        messages.success(request, 'Profile updated!')

    return redirect('profile', username=request.user.username)


@login_required
@require_POST
def instagram_generate(request):
    """
    Kicks off a Placid render job.
    Returns JSON {job_id, status}. Frontend polls instagram_status.
    """
    upload_folder = os.path.join(settings.MEDIA_ROOT, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    # Read form fields
    service        = request.POST.get('service', '').strip()
    client_name    = request.POST.get('client_name', '').strip()
    ig_handle      = request.POST.get('ig_handle', '').strip()
    template_id    = request.POST.get('template', '').strip()
    fmt            = request.POST.get('fmt', 'story')
    caption        = request.POST.get('caption', '').strip()
    hashtags       = request.POST.get('hashtags', '').strip()
    reservation_id = request.POST.get('reservation_id', None)
    photo          = request.FILES.get('photo')

    # Validation
    if not photo or photo.name == '':
        return JsonResponse({'error': 'Please upload a photo.'}, status=400)
    if not service:
        return JsonResponse({'error': 'Please enter the service performed.'}, status=400)
    if not template_id:
        return JsonResponse({'error': 'Please choose a template.'}, status=400)
    if fmt not in ('story', 'post_square', 'post_portrait'):
        fmt = 'story'

    tpl = placid.get_template(template_id)
    if not tpl:
        return JsonResponse({'error': 'Invalid template.'}, status=400)

    # Save uploaded photo
    filename   = photo.name.replace(' ', '_')
    timestamp  = datetime.now().strftime('%Y%m%d%H%M%S')
    safe_name  = f'{timestamp}_{filename}'
    photo_path = os.path.join(upload_folder, safe_name)

    with open(photo_path, 'wb+') as f:
        for chunk in photo.chunks():
            f.write(chunk)

    # Build public URL — Placid needs to fetch this from the internet
    base_url  = request.build_absolute_uri('/').rstrip('/')
    photo_url = f"{base_url}{settings.MEDIA_URL}uploads/{safe_name}"

    # Build layer payload
    profile, _  = MasterProfile.objects.get_or_create(user=request.user)
    master_name = (request.user.get_full_name() or request.user.username).strip()

    layers = placid.build_layer_payload(
        template_id = template_id,
        photo_url   = photo_url,
        service     = service,
        client_name = client_name,
        ig_handle   = ig_handle or profile.ig_handle or request.user.username,
        caption     = caption,
        hashtags    = hashtags,
        master_name = master_name,
        specialty   = profile.specialty,
        years_exp   = profile.years_exp,
        date_str    = date.today().strftime('%b %d, %Y'),
    )

    # Create PortfolioItem in pending state
    item = PortfolioItem.objects.create(
        user            = request.user,
        reservation_id  = int(reservation_id) if reservation_id else None,
        client_name     = client_name,
        service         = service,
        category        = profile.specialty or '',
        image           = safe_name,
        generated_image = '',                            # filled when ready
        template_style  = template_id,
        fmt             = fmt,
        caption         = caption,
        hashtags        = hashtags,
        date            = date.today().strftime('%b %d, %Y'),
    )

    # Kick off Placid render
    try:
        result = placid.create_image(template_id, layers)
    except Exception as e:
        return _pillow_fallback(item, photo_path, template_id, service,
                                ig_handle or request.user.username, fmt,
                                reservation_id, error=str(e))

    # Stash Placid job ID in session
    request.session[f'placid_job_{item.id}'] = {
        'placid_id': result.get('id'),
        'status':    result.get('status'),
    }
    request.session.modified = True

    # If Placid returned 'finished' immediately, download now
    if result.get('status') == 'finished' and result.get('image_url'):
        _finalize(item, result['image_url'])
        _mark_reservation(reservation_id, request.user)
        return JsonResponse({
            'job_id':    item.id,
            'status':    'finished',
            'image_url': f'{settings.MEDIA_URL}generated/{item.generated_image}',
        })

    return JsonResponse({
        'job_id': item.id,
        'status': result.get('status', 'queued'),
    })
    
    
@login_required
@require_GET
def instagram_status(request, job_id):
    """
    Polled by the frontend every 2 sec until status='finished' or 'error'.
    """
    item = get_object_or_404(PortfolioItem, id=job_id, user=request.user)

    # Already downloaded — return finished
    if item.generated_image:
        return JsonResponse({
            'status':    'finished',
            'image_url': f'{settings.MEDIA_URL}generated/{item.generated_image}',
            'caption':   item.caption,
            'hashtags':  item.hashtags,
        })

    session_key = f'placid_job_{item.id}'
    job = request.session.get(session_key)
    if not job:
        return JsonResponse({'status': 'error', 'error': 'Job not found.'}, status=404)

    placid_id = job.get('placid_id')
    if not placid_id:
        return JsonResponse({'status': 'error', 'error': 'No Placid ID stored.'}, status=500)

    # Poll Placid
    try:
        result = placid.check_status(placid_id)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=502)

    status = result.get('status')

    if status == 'finished' and result.get('image_url'):
        _finalize(item, result['image_url'])
        _mark_reservation(item.reservation_id, request.user)
        request.session.pop(session_key, None)
        request.session.modified = True
        return JsonResponse({
            'status':    'finished',
            'image_url': f'{settings.MEDIA_URL}generated/{item.generated_image}',
            'caption':   item.caption,
            'hashtags':  item.hashtags,
        })

    if status == 'error':
        item.delete()
        request.session.pop(session_key, None)
        request.session.modified = True
        return JsonResponse({'status': 'error',
                             'error': 'Placid render failed.'}, status=500)

    return JsonResponse({'status': status or 'processing'})

def _finalize(item, placid_image_url):
    """Download the finished Placid image and update the PortfolioItem."""
    generated_folder = os.path.join(settings.MEDIA_ROOT, 'generated')
    filename = placid.download_image(
        placid_image_url,
        output_dir    = generated_folder,
        filename_hint = item.template_style or 'ig',
    )
    item.generated_image = filename
    item.save(update_fields=['generated_image'])


def _mark_reservation(reservation_id, user):
    if not reservation_id:
        return
    try:
        res = Reservation.objects.filter(id=int(reservation_id), user=user).first()
        if res:
            res.has_portfolio = True
            res.save()
    except (ValueError, TypeError):
        pass


def _pillow_fallback(item, photo_path, template_id, service, ig_handle,
                    fmt, reservation_id, error=''):
    """If Placid fails, generate with Pillow so user still gets a result."""
    pillow_templates = ['stacked', 'editorial', 'coral', 'dark_minimal', 'split']
    idx              = abs(hash(template_id)) % len(pillow_templates)
    pillow_style     = pillow_templates[idx]

    generated_folder = os.path.join(settings.MEDIA_ROOT, 'generated')
    os.makedirs(generated_folder, exist_ok=True)
    timestamp      = datetime.now().strftime('%Y%m%d%H%M%S')
    base           = os.path.basename(photo_path).rsplit('.', 1)[0]
    generated_name = f'fallback_{timestamp}_{base}.png'
    generated_path = os.path.join(generated_folder, generated_name)

    try:
        generate_instagram_image(
            photo_path     = photo_path,
            output_path    = generated_path,
            template_style = pillow_style,
            service        = service,
            ig_handle      = ig_handle,
            fmt            = fmt,
        )
        item.generated_image = generated_name
        item.save(update_fields=['generated_image'])
        _mark_reservation(reservation_id, item.user)
        return JsonResponse({
            'job_id':    item.id,
            'status':    'finished',
            'image_url': f'{settings.MEDIA_URL}generated/{generated_name}',
            'fallback':  True,
            'warning':   'Used backup template — premium templates unavailable right now.',
        })
    except Exception as fallback_err:
        item.delete()
        return JsonResponse({
            'status': 'error',
            'error':  f'Generation failed: {error or fallback_err}',
        }, status=500)