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
    'story': [
        {'id': 'k2nuwsqxf3q40', 'name': 'Editorial',    'style': 'Bold magazine-style layout'},
        {'id': 'iewbvoab8dikx', 'name': 'Spotlight',    'style': 'Centered focus with clean type'},
        {'id': 'e25nljmewvxmx', 'name': 'Modern Frame', 'style': 'Photo with elegant text framing'},
        {'id': 'mktittyd33jrt', 'name': 'Minimal',      'style': 'Stripped-back, photo-first'},
        {'id': 'hi9dc9chdgxuh', 'name': 'Statement',    'style': 'High-contrast typography'},
        {'id': 'ogbvkisptqsf1', 'name': 'Premium',      'style': 'Refined luxury aesthetic'},
        {'id': 'pe8ynx1wuhq0w', 'name': 'Studio',       'style': 'Professional studio look'},
        {'id': 'rviapnflefgxu', 'name': 'Signature',    'style': 'Personal brand-forward design'},
        {'id': 'jsjiunyh3djzh', 'name': 'Classic',      'style': 'Timeless editorial composition'},
        {'id': 'qsmkbaxwkbd2e', 'name': 'Bold',         'style': 'Strong visual impact'},
        {'id': 'ddoq83iz9rgwc', 'name': 'Heritage',     'style': 'Craft-focused traditional feel'},
    ],
}


def get_template(template_id):
    """Return the template dict for a given id, or None."""
    for fmt in TEMPLATES.values():
        for tpl in fmt:
            if tpl['id'] == template_id:
                return tpl
    return None



def _truncate(text, max_len):
    if not text:
        return ''
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1].rstrip() + '…'



def build_layer_payload(template_id, *, photo_url, service, client_name,
                        ig_handle, caption, hashtags, master_name,
                        specialty, years_exp, date_str):

    handle = (ig_handle or '').lstrip('@') or 'stylebook'
    name   = (master_name or handle).strip()
    role   = specialty or 'Independent'

    return {
        'image':           {'image': photo_url},
        'date':            {'text':  date_str},
        'service_name':    {'text':  _truncate(service or 'Fresh work', 60)},
        'artist_name':     {'text':  _truncate(name, 40)},
        'artist_nickname': {'text':  f'@{handle}'},
        'artist_role':     {'text':  _truncate(role, 30)},
    }
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
    r = requests.get(url, headers=_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    return {
        'id':        data.get('id'),
        'status':    data.get('status'),
        'image_url': data.get('image_url'),
    }

def fetch_template_thumbnail(template_id):
    """
    Get the thumbnail URL for a template.
    Used by the picker to show real previews.
    Returns None if the template can't be fetched.
    """
    url = f'{PLACID_API_BASE}/templates/{template_id}'
    try:
        r = requests.get(url, headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json().get('thumbnail')
    except Exception:
        return None

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