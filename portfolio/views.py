import os
import base64
import io
import json
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from accounts.models import Certificate, Honor, WorkExperience
from accounts.models import WorkExperience

from .models import PortfolioItem
from .utils import generate_instagram_image           # Pillow fallback
from . import placid    
import cloudinary.uploader
from bookings.models import Reservation
from accounts.models import MasterProfile
from django.shortcuts import get_object_or_404
from django.urls import reverse

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

    days = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    return render(request, 'profile.html', {
        'active':           'profile',
        'profile_user':     profile_user,
        'is_own_profile':   is_own_profile,
        'portfolio_items':  portfolio_items[:6],
        'portfolio_count':  portfolio_count,
        'client_count':     client_count,
        'experience_items': experience_items,
        'days':             days,
    })

@login_required
def edit_profile(request):
    """
    GET  — render the edit form
    POST — save all profile fields, then redirect to the public profile
    """
    profile = request.user.profile

    if request.method == 'POST':
        # ── Existing fields ──
        profile.specialty = request.POST.get('specialty', '').strip()
        profile.bio       = request.POST.get('bio', '').strip()
        profile.skills    = request.POST.get('skills', '').strip()
        profile.ig_handle = request.POST.get('ig_handle', '').strip().lstrip('@')
        profile.location  = request.POST.get('location', '').strip()

        # ── New: contact ──
        profile.phone     = request.POST.get('phone', '').strip()

        # ── New: studio ──
        profile.studio_name = request.POST.get('studio_name', '').strip()

        # ── Numeric fields with safe parsing ──
        profile.years_exp         = _safe_int(request.POST.get('years_exp'))
        profile.years_at_location = _safe_int(request.POST.get('years_at_location'))
        profile.travel_radius_km  = _safe_int(request.POST.get('travel_radius_km'), allow_none=True)
        profile.pricing_from      = _safe_decimal(request.POST.get('pricing_from'))

        # ── Boolean ──
        profile.home_visits = request.POST.get('home_visits') == 'on'

        # ── Languages — comma-separated from frontend chip input ──
        raw_langs = request.POST.get('languages', '')
        profile.languages = [l.strip() for l in raw_langs.split(',') if l.strip()]

        # ── Working hours — JSON from per-day grid ──
        profile.working_hours = _parse_working_hours(request.POST)

        profile.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile', username=request.user.username)

# GET — render the edit form
    days = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    # Which tab to show — defaults to 'basic'
    tab = request.GET.get('tab', 'basic')
    if tab not in ('basic', 'experience', 'certificates', 'honors'):
        tab = 'basic'

    return render(request, 'edit_profile.html', {
        'active':         'profile',
        'profile':        profile,
        'working_hours':  profile.get_working_hours(),
        'languages_str':  ', '.join(profile.languages),
        'days':           days,
        'tab':            tab,
        'experiences':    profile.experiences.all(),
        'certificates':   profile.certificates.all(),
        'honors':         profile.honors.all(),
    })


import base64
import io


@login_required
@require_POST
def upload_avatar(request):
    """
    Accept a base64-encoded cropped image from the frontend,
    upload to Cloudinary, save URL to MasterProfile.avatar_url.
    """
    return _upload_profile_photo(
        request,
        kind='avatar',
        folder='stylebook/avatars',
        field_name='avatar_url',
    )


@login_required
@require_POST
def upload_cover(request):
    """
    Same flow as upload_avatar but for the cover banner.
    """
    return _upload_profile_photo(
        request,
        kind='cover',
        folder='stylebook/covers',
        field_name='cover_url',
    )



@login_required
@require_POST
def upload_certificate_file(request):
    """
    Upload a certificate file (PDF or image) to Cloudinary.
    Expects multipart form data with key 'file'.
    Returns JSON: {"url": "...", "kind": "image"|"pdf"}.
    """
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No file provided.'}, status=400)

    # Size check — 5MB max
    if f.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 5 MB.'}, status=400)

    # Type detection
    content_type = (f.content_type or '').lower()
    if content_type == 'application/pdf':
        kind = 'pdf'
        resource_type = 'raw'   # PDFs go to Cloudinary as 'raw' files
    elif content_type.startswith('image/'):
        kind = 'image'
        resource_type = 'image'
    else:
        return JsonResponse({'error': 'Only PDF or image files allowed.'}, status=400)

    try:
        result = cloudinary.uploader.upload(
            f,
            folder=f'stylebook/certificates/{request.user.id}',
            resource_type=resource_type,
        )
        url = result.get('secure_url')
    except Exception as e:
        return JsonResponse({'error': f'Upload failed: {e}'}, status=502)

    return JsonResponse({'url': url, 'kind': kind})


@login_required
@require_POST
def upload_honor_image(request):
    """
    Upload an honor image to Cloudinary.
    Expects multipart form data with key 'file'.
    Returns JSON: {"url": "..."}.
    """
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No file provided.'}, status=400)

    if f.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 5 MB.'}, status=400)

    content_type = (f.content_type or '').lower()
    if not content_type.startswith('image/'):
        return JsonResponse({'error': 'Only image files allowed.'}, status=400)

    try:
        result = cloudinary.uploader.upload(
            f,
            folder=f'stylebook/honors/{request.user.id}',
            resource_type='image',
        )
        url = result.get('secure_url')
    except Exception as e:
        return JsonResponse({'error': f'Upload failed: {e}'}, status=502)

    return JsonResponse({'url': url})


def _upload_profile_photo(request, *, kind, folder, field_name):
    """
    Shared logic for avatar + cover uploads.

    Expects POST body: {"image_data": "data:image/png;base64,iVBORw..."}
    Returns JSON: {"url": "<cloudinary_url>"} on success
    """
    image_data = request.POST.get('image_data', '')
    if not image_data:
        return JsonResponse({'error': 'No image data provided.'}, status=400)

    # Strip the "data:image/png;base64," prefix if present
    if ',' in image_data:
        image_data = image_data.split(',', 1)[1]

    try:
        binary = base64.b64decode(image_data)
    except Exception:
        return JsonResponse({'error': 'Invalid base64 image data.'}, status=400)

    # Upload to Cloudinary
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(binary),
            folder=folder,
            public_id=f'{kind}_{request.user.id}',
            overwrite=True,
            resource_type='image',
        )
        url = result.get('secure_url')
    except Exception as e:
        return JsonResponse({'error': f'Cloudinary upload failed: {e}'}, status=502)

    if not url:
        return JsonResponse({'error': 'No URL returned from Cloudinary.'}, status=502)

    # Save URL to profile
    profile, _ = MasterProfile.objects.get_or_create(user=request.user)
    setattr(profile, field_name, url)
    profile.save(update_fields=[field_name])

    return JsonResponse({'url': url})


def _safe_int(value, allow_none=False):
    """Parse string → int. Returns 0 (or None if allow_none) on failure."""
    if value is None or value == '':
        return None if allow_none else 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return None if allow_none else 0


def _safe_decimal(value):
    """Parse string → Decimal. Returns None on failure (for nullable money fields)."""
    if value is None or value == '':
        return None
    try:
        from decimal import Decimal, InvalidOperation
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _parse_working_hours(post_data):
    """
    Read the 7-day grid from POST data and build the JSON structure.
    Form sends fields like:
        mon_open, mon_close, mon_closed (checkbox)
        tue_open, tue_close, tue_closed
        ...
    """
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    hours = {}
    for d in days:
        closed = post_data.get(f'{d}_closed') == 'on'
        hours[d] = {
            'open':   post_data.get(f'{d}_open', '09:00'),
            'close':  post_data.get(f'{d}_close', '18:00'),
            'closed': closed,
        }
    return hours


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
    caption        = request.POST.get('caption', '').strip()
    hashtags       = request.POST.get('hashtags', '').strip()
    reservation_id = request.POST.get('reservation_id', None)
    photo          = request.FILES.get('photo')

    fmt = 'story'

    if not photo or photo.name == '':
        return JsonResponse({'error': 'Please upload a photo.'}, status=400)
    if not service:
        return JsonResponse({'error': 'Please enter the service performed.'}, status=400)
    if not template_id:
        return JsonResponse({'error': 'Please choose a template.'}, status=400)

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

    # Upload to Cloudinary so Placid can fetch a public URL
    try:
        upload_result = cloudinary.uploader.upload(
            photo_path,
            folder='stylebook/uploads',
            public_id=safe_name.rsplit('.', 1)[0],   # strip extension
            overwrite=True,
            resource_type='image',
        )
        photo_url = upload_result.get('secure_url')
    except Exception as e:
        # Cloudinary failed — fall back to Pillow immediately
        return _pillow_fallback(
            None, photo_path, template_id, service,
            ig_handle or request.user.username, fmt,
            reservation_id, error=f'Cloudinary upload failed: {e}',
        )

    if not photo_url:
        return _pillow_fallback(
            None, photo_path, template_id, service,
            ig_handle or request.user.username, fmt,
            reservation_id, error='Cloudinary returned no URL',
        )

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
    # If Placid returned 'finished' immediately, download now
    if result.get('status') == 'finished' and result.get('image_url'):
        _finalize(item, result['image_url'])
        _mark_reservation(reservation_id, request.user)
        return JsonResponse({
            'job_id':    item.id,
            'status':    'finished',
            'image_url': _image_url_for(item.generated_image),
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
            'image_url': _image_url_for(item.generated_image),
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
            'image_url': _image_url_for(item.generated_image),
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


@cache_page(60 * 60 * 24)  # cache 24 hours
def template_thumbnail(request, template_id):
    """
    Returns a redirect to the Placid thumbnail URL for the given template.
    Cached for 24h so we don't hammer Placid's API.

    Public endpoint — anyone hitting the instagram page can load thumbnails.
    """
    # Verify it's one of our templates (don't proxy arbitrary IDs)
    if not placid.get_template(template_id):
        return JsonResponse({'error': 'Unknown template.'}, status=404)

    thumb_url = placid.fetch_template_thumbnail(template_id)
    if not thumb_url:
        return JsonResponse({'error': 'Thumbnail unavailable.'}, status=502)

    return HttpResponseRedirect(thumb_url)


def _image_url_for(value):

    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    return f'{settings.MEDIA_URL}generated/{value}'


def _finalize(item, placid_image_url):
    """
    Placid has rendered the image. Upload the result to Cloudinary
    so it survives container restarts, and store the public URL.
    """
    try:
        up = cloudinary.uploader.upload(
            placid_image_url,                          # Cloudinary can fetch from URL
            folder='stylebook/generated',
            public_id=f'placid_{item.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}',
            overwrite=True,
            resource_type='image',
        )
        item.generated_image = up.get('secure_url') or placid_image_url
    except Exception:
        # If Cloudinary upload fails, store Placid's CDN URL directly.
        # It won't survive forever but works short-term.
        item.generated_image = placid_image_url

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
    idx              = abs(hash(template_id or 'x')) % len(pillow_templates)
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

        # Upload the generated image to Cloudinary too so it's publicly viewable
        try:
            up = cloudinary.uploader.upload(
                generated_path,
                folder='stylebook/generated',
                public_id=generated_name.rsplit('.', 1)[0],
                overwrite=True,
                resource_type='image',
            )
            cloudinary_url = up.get('secure_url') or ''
        except Exception:
            cloudinary_url = ''

        # If we already have a PortfolioItem, update it. Otherwise create one.
        if item:
            item.generated_image = cloudinary_url or generated_name
            item.save(update_fields=['generated_image'])
        else:
            # Item wasn't created yet (Cloudinary upload of original failed)
            # Don't create one here — user will need to retry
            pass

        if item:
            _mark_reservation(reservation_id, item.user)

        final_url = cloudinary_url or f'{settings.MEDIA_URL}generated/{generated_name}'
        return JsonResponse({
            'job_id':    item.id if item else 0,
            'status':    'finished',
            'image_url': final_url,
            'fallback':  True,
            'warning':   'Used backup template — premium templates unavailable right now.',
        })
    except Exception as fallback_err:
        if item:
            item.delete()
        return JsonResponse({
            'status': 'error',
            'error':  f'Generation failed: {error or fallback_err}',
        }, status=500)
        
        
        
from accounts.models import WorkExperience


# ════════════════════════════════════════════════
# WorkExperience — Create / Update / Delete
# ════════════════════════════════════════════════

def _parse_work_experience(post_data):
    """Extract WorkExperience fields from POST data with validation."""
    title       = post_data.get('title', '').strip()
    studio_name = post_data.get('studio_name', '').strip()
    city        = post_data.get('city', '').strip()
    description = post_data.get('description', '').strip()
    is_current  = post_data.get('is_current') == 'on'

    try:
        start_month = int(post_data.get('start_month', 0))
        start_year  = int(post_data.get('start_year', 0))
    except (ValueError, TypeError):
        return None, 'Invalid start date.'

    if not (1 <= start_month <= 12) or start_year < 1950 or start_year > 2100:
        return None, 'Invalid start month or year.'

    end_month = None
    end_year  = None
    if not is_current:
        try:
            end_month = int(post_data.get('end_month', 0))
            end_year  = int(post_data.get('end_year', 0))
        except (ValueError, TypeError):
            return None, 'Invalid end date.'
        if not (1 <= end_month <= 12) or end_year < 1950 or end_year > 2100:
            return None, 'Invalid end month or year.'

    if not title:
        return None, 'Title is required.'

    return {
        'title':       title,
        'studio_name': studio_name,
        'city':        city,
        'start_month': start_month,
        'start_year':  start_year,
        'end_month':   end_month,
        'end_year':    end_year,
        'is_current':  is_current,
        'description': description,
    }, None


@login_required
@require_POST
def experience_add(request):
    """Create a new WorkExperience for the current user."""
    fields, err = _parse_work_experience(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=experience")

    WorkExperience.objects.create(profile=request.user.profile, **fields)
    messages.success(request, 'Experience added.')
    return redirect(f"{reverse('profile_edit')}?tab=experience")


@login_required
@require_POST
def experience_edit(request, pk):
    """Update an existing WorkExperience."""
    exp = get_object_or_404(WorkExperience, pk=pk, profile=request.user.profile)
    fields, err = _parse_work_experience(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=experience")

    for key, value in fields.items():
        setattr(exp, key, value)
    exp.save()
    messages.success(request, 'Experience updated.')
    return redirect(f"{reverse('profile_edit')}?tab=experience")


@login_required
@require_POST
def experience_delete(request, pk):
    """Delete a WorkExperience."""
    exp = get_object_or_404(WorkExperience, pk=pk, profile=request.user.profile)
    exp.delete()
    messages.success(request, 'Experience removed.')
    return redirect(f"{reverse('profile_edit')}?tab=experience")


# ════════════════════════════════════════════════
# Certificate — Create / Update / Delete
# ════════════════════════════════════════════════

def _parse_certificate(post_data):
    """Extract Certificate fields from POST data."""
    name        = post_data.get('name', '').strip()
    institution = post_data.get('institution', '').strip()
    file_url    = post_data.get('file_url', '').strip()
    file_kind   = post_data.get('file_kind', '').strip()

    try:
        year = int(post_data.get('year', 0))
    except (ValueError, TypeError):
        return None, 'Invalid year.'

    if year < 1950 or year > 2100:
        return None, 'Invalid year.'
    if not name:
        return None, 'Certificate name is required.'
    if not institution:
        return None, 'Institution is required.'

    return {
        'name':        name,
        'institution': institution,
        'year':        year,
        'file_url':    file_url,
        'file_kind':   file_kind,
    }, None


@login_required
@require_POST
def certificate_add(request):
    """Create a new Certificate."""
    fields, err = _parse_certificate(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=certificates")

    Certificate.objects.create(profile=request.user.profile, **fields)
    messages.success(request, 'Certificate added.')
    return redirect(f"{reverse('profile_edit')}?tab=certificates")


@login_required
@require_POST
def certificate_edit(request, pk):
    """Update an existing Certificate."""
    cert = get_object_or_404(Certificate, pk=pk, profile=request.user.profile)
    fields, err = _parse_certificate(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=certificates")

    for key, value in fields.items():
        setattr(cert, key, value)
    cert.save()
    messages.success(request, 'Certificate updated.')
    return redirect(f"{reverse('profile_edit')}?tab=certificates")


@login_required
@require_POST
def certificate_delete(request, pk):
    """Delete a Certificate."""
    cert = get_object_or_404(Certificate, pk=pk, profile=request.user.profile)
    cert.delete()
    messages.success(request, 'Certificate removed.')
    return redirect(f"{reverse('profile_edit')}?tab=certificates")


# ════════════════════════════════════════════════
# Honor — Create / Update / Delete
# ════════════════════════════════════════════════

def _parse_honor(post_data):
    """Extract Honor fields from POST data."""
    title       = post_data.get('title', '').strip()
    issuer      = post_data.get('issuer', '').strip()
    description = post_data.get('description', '').strip()
    image_url   = post_data.get('image_url', '').strip()

    try:
        year = int(post_data.get('year', 0))
    except (ValueError, TypeError):
        return None, 'Invalid year.'

    if year < 1950 or year > 2100:
        return None, 'Invalid year.'
    if not title:
        return None, 'Honor title is required.'

    return {
        'title':       title,
        'issuer':      issuer,
        'year':        year,
        'description': description,
        'image_url':   image_url,
    }, None


@login_required
@require_POST
def honor_add(request):
    """Create a new Honor."""
    fields, err = _parse_honor(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=honors")

    Honor.objects.create(profile=request.user.profile, **fields)
    messages.success(request, 'Honor added.')
    return redirect(f"{reverse('profile_edit')}?tab=honors")


@login_required
@require_POST
def honor_edit(request, pk):
    """Update an existing Honor."""
    honor = get_object_or_404(Honor, pk=pk, profile=request.user.profile)
    fields, err = _parse_honor(request.POST)
    if err:
        messages.error(request, err)
        return redirect(f"{reverse('profile_edit')}?tab=honors")

    for key, value in fields.items():
        setattr(honor, key, value)
    honor.save()
    messages.success(request, 'Honor updated.')
    return redirect(f"{reverse('profile_edit')}?tab=honors")


@login_required
@require_POST
def honor_delete(request, pk):
    """Delete an Honor."""
    honor = get_object_or_404(Honor, pk=pk, profile=request.user.profile)
    honor.delete()
    messages.success(request, 'Honor removed.')
    return redirect(f"{reverse('profile_edit')}?tab=honors")