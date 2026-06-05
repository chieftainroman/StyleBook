"""
Placid API client for StyleBook.

Flow:
    1. create_image()   → POSTs job, returns {placid_id, status}
    2. check_status()   → polls until status == 'finished'
    3. download_image() → fetches PNG from Placid CDN to media/generated/
"""

import os
import uuid
import requests
from datetime import datetime
from django.conf import settings


PLACID_API_BASE = "https://api.placid.app/api/rest"


# ────────────────────────────────────────────────────────
# Template catalog
# ────────────────────────────────────────────────────────

TEMPLATES = {
    # ── STORY (1080 × 1920) ────────────────────────────
    'story': [
        {'id': 'ujlnwwfiacd1r', 'name': 'Speaker',   'style': 'Bold speaker card with dots'},
        {'id': 'tbbjszqtrpwqt', 'name': 'Overlay',   'style': 'Photo with title overlay'},
        {'id': '3crzha4apotrf', 'name': 'Episode',   'style': 'Clean editorial with episode number'},
        {'id': 'ayur8gz580kiq', 'name': 'Swipe',     'style': 'Bold sale-style with swipe CTA'},
        {'id': 'u6sulxy5dplqr', 'name': 'Stats',     'style': 'Four metric cards with photo'},
        {'id': 'rjkvb0ujn3lrm', 'name': 'Polaroid',  'style': 'Polaroid photo with headline'},
    ],

    # ── POST SQUARE (1080 × 1080) ──────────────────────
    'post_square': [
        {'id': '7fmqyqmbcmhb4', 'name': 'Detail Card', 'style': 'Property-style with three info chips'},
        {'id': 'ufvfevjzrq6gx', 'name': 'Speaker',     'style': 'Square speaker card'},
        {'id': 'hnfgrekv5dyq8', 'name': 'Episode',     'style': 'Minimal podcast-style square'},
        {'id': '3jtnxqcirg29e', 'name': 'Stats',       'style': 'Four metric cards square'},
        {'id': 'bc1pos33b16zk', 'name': 'Overlay',     'style': 'Photo overlay with title'},
        {'id': 'tvzcd1igqec3p', 'name': 'Circles',     'style': 'Geometric circles with logo'},
        {'id': 'es6fwbrljed9e', 'name': 'Promo',       'style': 'Bold promo with pattern background'},
        {'id': 'grzqbvdrgmekl', 'name': 'Divider',     'style': 'Clean minimal with divider line'},
        {'id': 'yvfimi1my6lyo', 'name': 'Polaroid',    'style': 'Square polaroid layout'},
        {'id': '9mxi8sjyhp4yf', 'name': 'Talk',        'style': 'Speaker talk-style with pattern'},
    ],
}


def get_template(template_id):
    """Return the template dict for a given id, or None."""
    for fmt in TEMPLATES.values():
        for tpl in fmt:
            if tpl['id'] == template_id:
                return tpl
    return None


# ────────────────────────────────────────────────────────
# Layer mapping
# ────────────────────────────────────────────────────────
# Categorize the layer names seen across all 16 templates.
# Any layer not listed here is left alone (template default).

IMAGE_LAYERS = {
    'photo', 'img', 'img-bg', 'speaker-img', 'speaker photo', 'polaroid',
}
TITLE_LAYERS = {
    'title', 'headline', 'webinar-title', 'podcast-title',
    'workout-title', 'talk-title', 'talk title', 'img-title',
}
SUBTITLE_LAYERS = {
    'subtitle', 'subline', 'webinar-tagline', 'webinar-taglin',
    'episode-title', 'tagline',
}
NAME_LAYERS     = {'speaker-name', 'speaker name', 'user', 'username'}
POSITION_LAYERS = {'speaker-position', 'listen-to', 'episode-number', 'position'}
CTA_LAYERS      = {'cta', 'cta-text'}
LOGO_LAYERS     = {'logo', 'logo-text'}
INFO_LAYERS     = {'info', 'description'}
SALE_LAYERS     = {'sale'}
PRICE_LAYERS    = {'price'}
ROOMS_LAYERS    = {'rooms'}
SIZE_LAYERS     = {'size'}

def _truncate(text, max_len):
    if not text:
        return ''
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1].rstrip() + '…'


def _first_sentence(text, max_len=80):
    """First sentence of caption, capped at max_len."""
    if not text:
        return ''
    text = text.strip()
    for sep in ['. ', '! ', '? ', '\n']:
        if sep in text:
            first = text.split(sep)[0] + sep.strip()
            return _truncate(first, max_len)
    return _truncate(text, max_len)


def build_layer_payload(template_id, *, photo_url, service, client_name,
                        ig_handle, caption, hashtags, master_name,
                        specialty, years_exp, date_str):
    """
    Build the `layers` dict for Placid given form data.

    Returns dict like:
        {'title': {'text': 'Skin fade'}, 'photo': {'image': 'https://...'}}
    """
    handle = (ig_handle or '').lstrip('@') or 'stylebook'
    spec   = specialty or 'Independent'
    years  = years_exp or 0

    spec_line = f"{spec} · {years} yr" if years > 0 else spec

    # Stat cards (workout templates)
    stat_data = [
        {'title': 'Service', 'value': _truncate(service, 14), 'unit': ''},
        {'title': 'Style',   'value': spec[:14],              'unit': ''},
        {'title': 'Date',    'value': date_str.split(',')[0], 'unit': ''},
        {'title': 'Book',    'value': f'@{handle}'[:14],      'unit': ''},
    ]

    name      = master_name or handle
    cap_short = _first_sentence(caption, 60) if caption else spec_line

    layers = {}

    # Image layers
    for layer in IMAGE_LAYERS:
        layers[layer] = {'image': photo_url}

    # Text layers
    for layer in TITLE_LAYERS:
        layers[layer] = {'text': _truncate(service, 50)}
    for layer in SUBTITLE_LAYERS:
        layers[layer] = {'text': cap_short}
    for layer in NAME_LAYERS:
        layers[layer] = {'text': name}
    for layer in POSITION_LAYERS:
        layers[layer] = {'text': spec_line}
    for layer in CTA_LAYERS:
        layers[layer] = {'text': f'@{handle}'}
    for layer in LOGO_LAYERS:
        layers[layer] = {'text': 'StyleBook'}
    for layer in INFO_LAYERS:
        layers[layer] = {'text': cap_short or service}
    for layer in SALE_LAYERS:
        layers[layer] = {'text': 'FRESH'}
    for layer in PRICE_LAYERS:
        layers[layer] = {'text': f'@{handle}'}
    for layer in ROOMS_LAYERS:
        layers[layer] = {'text': _truncate(service, 16)}
    for layer in SIZE_LAYERS:
        layers[layer] = {'text': spec_line}

    # Workout stat cards
    for i, stat in enumerate(stat_data, start=1):
        layers[f'title-{i}'] = {'text': stat['title']}
        layers[f'value-{i}'] = {'text': stat['value']}
        layers[f'unit-{i}']  = {'text': stat['unit']}

    return layers


# ────────────────────────────────────────────────────────
# Placid API calls
# ────────────────────────────────────────────────────────

def _headers():
    token = getattr(settings, 'PLACID_API_KEY', '') or os.environ.get('PLACID_API_KEY', '')
    if not token:
        raise RuntimeError('PLACID_API_KEY is not configured.')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type':  'application/json',
    }


def create_image(template_id, layers):
    """POST to Placid → returns {id, status, image_url}."""
    url     = f'{PLACID_API_BASE}/images'
    payload = {'template_uuid': template_id, 'layers': layers}

    r = requests.post(url, headers=_headers(), json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    return {
        'id':          data.get('id'),
        'status':      data.get('status'),
        'image_url':   data.get('image_url'),
        'polling_url': data.get('polling_url'),
    }


def check_status(placid_id):
    """GET /images/{id} → returns current status + image_url when finished."""
    url = f'{PLACID_API_BASE}/images/{placid_id}'
    r   = requests.get(url, headers=_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    return {
        'id':        data.get('id'),
        'status':    data.get('status'),
        'image_url': data.get('image_url'),
    }


def download_image(image_url, output_dir, filename_hint='ig'):
    """Download a finished Placid image to media/generated/."""
    os.makedirs(output_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d%H%M%S')
    short_id = uuid.uuid4().hex[:6]
    filename = f'placid_{ts}_{short_id}_{filename_hint}.png'
    path     = os.path.join(output_dir, filename)

    r = requests.get(image_url, stream=True, timeout=60)
    r.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return filename