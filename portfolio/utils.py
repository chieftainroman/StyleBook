import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


FORMATS = {
    'story':         {'w': 1080, 'h': 1920},
    'post_portrait': {'w': 1080, 'h': 1350},
    'post_square':   {'w': 1080, 'h': 1080},
}


# ── Font loader ────────────────────────────────────────
def _load_fonts():
    candidates_bold = [
        os.path.join(os.path.dirname(__file__), 'fonts', 'Inter-Bold.ttf'),
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    candidates_regular = [
        os.path.join(os.path.dirname(__file__), 'fonts', 'Inter-Regular.ttf'),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    def find(paths):
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    bold_path    = find(candidates_bold)
    regular_path = find(candidates_regular)

    def font(size, bold=False):
        path = bold_path if bold else regular_path
        if path:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    return font


# ── Helpers ────────────────────────────────────────────
def _prepare_photo(photo_path, target_w, target_h):
    """Open, fix EXIF orientation, crop to fill target dimensions."""
    img = Image.open(photo_path).convert('RGB')
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio    = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left  = (src_w - new_w) // 2
        img   = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top   = (src_h - new_h) // 2
        img   = img.crop((0, top, src_w, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def _strong_gradient(size, start_frac=0.40, end_alpha=245):
    """Strong bottom gradient — goes from transparent to near-black.
    start_frac: where gradient begins (0.40 = starts at 40% down)
    end_alpha: how dark at the very bottom (245 = almost full black)
    """
    w, h   = size
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    start_y = int(h * start_frac)
    zone_h  = h - start_y

    for y in range(start_y, h):
        t     = (y - start_y) / zone_h        # 0 → 1
        alpha = int(t * t * end_alpha)         # quadratic — subtle start, strong end
        draw.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, alpha))

    return overlay


def _top_vignette(size, depth=0.18, alpha=120):
    """Soft top gradient for handle/logo area."""
    w, h    = size
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    zone_h  = int(h * depth)

    for y in range(zone_h):
        t     = 1 - (y / zone_h)
        a     = int(t * alpha)
        draw.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, a))

    return overlay


def _draw_text_shadow(draw, pos, text, font, fill, shadow_offset=3, shadow_alpha=160):
    """Draw text with a subtle drop shadow for readability."""
    sx, sy = pos[0] + shadow_offset, pos[1] + shadow_offset
    draw.text((sx, sy), text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text(pos, text, font=font, fill=fill)


def _wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width pixels."""
    words  = text.split()
    lines  = []
    current = ''

    for word in words:
        test = (current + ' ' + word).strip()
        bb   = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def _pill_badge(draw, text, font, x, y, bg_color, text_color, padding_x=24, padding_h=16):
    """Draw a rounded pill badge."""
    bb     = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    bw     = tw + padding_x * 2
    bh     = th + padding_h * 2
    radius = bh // 2
    draw.rounded_rectangle(
        [(x, y), (x + bw, y + bh)],
        radius=radius,
        fill=bg_color
    )
    draw.text(
        (x + padding_x - bb[0], y + padding_h - bb[1]),
        text, font=font, fill=text_color
    )
    return bw, bh


# ── TEMPLATE 1: Stacked Bold ──────────────────────────
# Full-bleed photo. Strong bottom gradient.
# Large stacked typography. Handle top-right.
def tpl_stacked(photo_path, fmt, service, ig_handle):
    dim  = FORMATS[fmt]
    w, h = dim['w'], dim['h']
    font = _load_fonts()

    # Base photo
    canvas = _prepare_photo(photo_path, w, h).convert('RGBA')

    # Gradients
    canvas = Image.alpha_composite(canvas, _top_vignette((w, h)))
    canvas = Image.alpha_composite(canvas, _strong_gradient((w, h), 0.38, 250))
    draw   = ImageDraw.Draw(canvas)

    pad = int(w * 0.07)

    # Sizes — scale with canvas
    f_handle  = font(int(w * 0.030))
    f_big     = font(int(w * 0.115), bold=True)
    f_service = font(int(w * 0.038), bold=True)

    # Handle — top left
    draw.text((pad, int(h * 0.042)),
              f"@{ig_handle}", font=f_handle, fill=(255, 255, 255, 200))

    # Three stacked words
    line_h = int(w * 0.118)
    base_y = int(h * 0.60)

    draw.text((pad, base_y),
              "TODAY", font=f_big, fill=(233, 96, 60))           # coral
    draw.text((pad, base_y + line_h),
              "I DID",  font=f_big, fill=(255, 255, 255))
    draw.text((pad, base_y + line_h * 2),
              "THAT",   font=f_big, fill=(180, 180, 180))

    # Service — below the words
    service_y = base_y + line_h * 3 + int(h * 0.012)
    lines = _wrap_text(service, f_service, w - pad * 2, draw)
    for i, line in enumerate(lines[:2]):
        draw.text((pad, service_y + i * int(w * 0.045)),
                  line, font=f_service, fill=(220, 220, 220))

    # StyleBook watermark — bottom right
    f_wm = font(int(w * 0.024))
    wm   = "StyleBook"
    bb   = draw.textbbox((0, 0), wm, font=f_wm)
    draw.text((w - (bb[2] - bb[0]) - pad, h - int(h * 0.025) - (bb[3] - bb[1])),
              wm, font=f_wm, fill=(255, 255, 255, 120))

    return canvas.convert('RGB')


# ── TEMPLATE 2: Editorial ─────────────────────────────
# Photo fills frame. Subtle dark wash.
# "MASTER OF WORK" badge bottom-left. Service in large serif-style bold.
# Clean minimal layout — photographer-style.
def tpl_editorial(photo_path, fmt, service, ig_handle):
    dim  = FORMATS[fmt]
    w, h = dim['w'], dim['h']
    font = _load_fonts()

    canvas = _prepare_photo(photo_path, w, h).convert('RGBA')
    canvas = Image.alpha_composite(canvas, _top_vignette((w, h), depth=0.15, alpha=140))
    canvas = Image.alpha_composite(canvas, _strong_gradient((w, h), 0.42, 255))
    draw   = ImageDraw.Draw(canvas)

    pad = int(w * 0.07)

    f_badge   = font(int(w * 0.028), bold=True)
    f_service = font(int(w * 0.068), bold=True)
    f_sub     = font(int(w * 0.032))
    f_handle  = font(int(w * 0.028))

    # Handle — top left
    draw.text((pad, int(h * 0.042)),
              f"@{ig_handle}", font=f_handle, fill=(255, 255, 255, 200))

    # Service — large, near bottom
    lines  = _wrap_text(service, f_service, w - pad * 2, draw)
    line_h = int(w * 0.075)
    total  = len(lines[:3]) * line_h
    svc_y  = h - int(h * 0.18) - total

    for i, line in enumerate(lines[:3]):
        _draw_text_shadow(
            draw, (pad, svc_y + i * line_h),
            line, f_service, (255, 255, 255)
        )

    # "MASTER OF WORK" badge above service
    badge_y = svc_y - int(h * 0.055)
    _pill_badge(draw, "MASTER OF WORK", f_badge,
                pad, badge_y,
                bg_color=(233, 96, 60),
                text_color=(255, 255, 255))

    # Date-style subtext below service
    sub_y = h - int(h * 0.085)
    draw.text((pad, sub_y), "StyleBook · Fresh work",
              font=f_sub, fill=(180, 180, 180))

    return canvas.convert('RGB')


# ── TEMPLATE 3: Coral Bold ────────────────────────────
# Split layout — top 55% is solid coral with text, bottom 45% is photo.
# High contrast, bold, graphic feel. Very thumb-stopping.
def tpl_coral(photo_path, fmt, service, ig_handle):
    dim  = FORMATS[fmt]
    w, h = dim['w'], dim['h']
    font = _load_fonts()

    # Coral background
    canvas = Image.new('RGB', (w, h), (220, 75, 45))
    draw   = ImageDraw.Draw(canvas)

    pad      = int(w * 0.08)
    photo_y  = int(h * 0.52)
    photo_h  = h - photo_y

    # Photo pasted in bottom portion — with a slight top overlap
    photo    = _prepare_photo(photo_path, w, photo_h + int(h * 0.04))
    canvas.paste(photo, (0, photo_y - int(h * 0.04)))

    # Gradient bridging the split
    bridge = Image.new('RGBA', (w, int(h * 0.12)), (0, 0, 0, 0))
    bd     = ImageDraw.Draw(bridge)
    for y in range(int(h * 0.12)):
        t = y / (h * 0.12)
        a = int(t * 80)
        bd.rectangle([(0, y), (w, y + 1)], fill=(220, 75, 45, 255 - a))
    canvas.paste(bridge.convert('RGB'), (0, photo_y - int(h * 0.06)),
                 mask=bridge.split()[3])

    draw = ImageDraw.Draw(canvas)

    f_logo    = font(int(w * 0.032), bold=True)
    f_headline= font(int(w * 0.088), bold=True)
    f_service = font(int(w * 0.038))
    f_cta     = font(int(w * 0.032), bold=True)

    # Logo top-left
    draw.text((pad, int(h * 0.042)),
              "StyleBook", font=f_logo, fill=(255, 220, 200))

    # Big headline
    hl_y   = int(h * 0.10)
    hl_lh  = int(w * 0.095)
    draw.text((pad, hl_y),          "FRESH",    font=f_headline, fill=(255, 255, 255))
    draw.text((pad, hl_y + hl_lh),  "FROM THE", font=f_headline, fill=(30, 20, 10))
    draw.text((pad, hl_y + hl_lh*2),"CHAIR.",   font=f_headline, fill=(255, 255, 255))

    # Service text
    svc_y = hl_y + hl_lh * 3 + int(h * 0.012)
    lines = _wrap_text(service, f_service, w - pad * 2, draw)
    for i, line in enumerate(lines[:2]):
        draw.text((pad, svc_y + i * int(w * 0.044)),
                  line, font=f_service, fill=(255, 235, 220))

    # CTA at very bottom
    cta  = f"Book now · @{ig_handle}"
    bb   = draw.textbbox((0, 0), cta, font=f_cta)
    cx   = (w - (bb[2] - bb[0])) // 2
    draw.text((cx, h - int(h * 0.038)),
              cta, font=f_cta, fill=(255, 255, 255))

    return canvas


# ── TEMPLATE 4: Dark Minimal ──────────────────────────
# Full-bleed photo, dark overlay, single large word in gold + service.
# Most "luxury barber" feeling.
def tpl_dark_minimal(photo_path, fmt, service, ig_handle):
    dim  = FORMATS[fmt]
    w, h = dim['w'], dim['h']
    font = _load_fonts()

    canvas = _prepare_photo(photo_path, w, h).convert('RGBA')

    # Dark overlay — not a gradient, a consistent 55% wash
    wash = Image.new('RGBA', (w, h), (10, 10, 10, 140))
    canvas = Image.alpha_composite(canvas, wash)
    canvas = Image.alpha_composite(canvas, _strong_gradient((w, h), 0.35, 255))
    canvas = Image.alpha_composite(canvas, _top_vignette((w, h), 0.20, 160))
    draw   = ImageDraw.Draw(canvas)

    pad = int(w * 0.07)

    f_handle  = font(int(w * 0.030))
    f_word    = font(int(w * 0.160), bold=True)
    f_service = font(int(w * 0.042), bold=True)
    f_sub     = font(int(w * 0.028))

    # Handle top
    draw.text((pad, int(h * 0.042)),
              f"@{ig_handle}", font=f_handle, fill=(200, 200, 200))

    # Single large gold word centered
    word  = "DONE."
    bb    = draw.textbbox((0, 0), word, font=f_word)
    cx    = (w - (bb[2] - bb[0])) // 2
    cy    = int(h * 0.38)
    draw.text((cx, cy), word, font=f_word, fill=(201, 169, 110))  # gold

    # Service below
    lines  = _wrap_text(service, f_service, w - pad * 2, draw)
    svc_y  = int(h * 0.73)
    lh     = int(w * 0.050)
    for i, line in enumerate(lines[:3]):
        draw.text((pad, svc_y + i * lh),
                  line, font=f_service, fill=(255, 255, 255))

    # Thin gold line above service
    line_y = svc_y - int(h * 0.018)
    draw.rectangle([(pad, line_y), (int(w * 0.25), line_y + 3)],
                   fill=(201, 169, 110))

    # StyleBook bottom
    f_wm = font(int(w * 0.025))
    wm   = "StyleBook"
    bb   = draw.textbbox((0, 0), wm, font=f_wm)
    draw.text((w - (bb[2] - bb[0]) - pad, h - int(h * 0.025) - (bb[3] - bb[1])),
              wm, font=f_wm, fill=(201, 169, 110, 150))

    return canvas.convert('RGB')


# ── TEMPLATE 5: Split Stats ───────────────────────────
# Left half dark with stats text, right half photo.
# Great for "X clients this month" type posts.
def tpl_split(photo_path, fmt, service, ig_handle):
    dim  = FORMATS[fmt]
    w, h = dim['w'], dim['h']
    font = _load_fonts()

    canvas = Image.new('RGB', (w, h), (18, 18, 16))
    draw   = ImageDraw.Draw(canvas)

    # Photo on right half
    split_x  = int(w * 0.48)
    photo_w  = w - split_x
    photo    = _prepare_photo(photo_path, photo_w, h)
    canvas.paste(photo, (split_x, 0))

    # Gradient over photo left edge for smooth blend
    blend = Image.new('RGBA', (int(w * 0.20), h), (0, 0, 0, 0))
    bd    = ImageDraw.Draw(blend)
    for x in range(int(w * 0.20)):
        t = 1 - (x / (w * 0.20))
        a = int(t * 220)
        bd.rectangle([(x, 0), (x + 1, h)], fill=(18, 18, 16, a))
    canvas.paste(Image.new('RGB', (int(w * 0.20), h), (18, 18, 16)),
                 (split_x, 0), mask=blend.split()[3])

    draw = ImageDraw.Draw(canvas)
    pad  = int(w * 0.07)

    f_handle  = font(int(w * 0.028))
    f_label   = font(int(w * 0.030), bold=True)
    f_service = font(int(w * 0.042), bold=True)
    f_wm      = font(int(w * 0.025))

    # StyleBook logo top
    draw.text((pad, int(h * 0.042)),
              "StyleBook", font=f_handle, fill=(201, 169, 110))

    # Gold accent bar
    bar_y = int(h * 0.12)
    draw.rectangle([(pad, bar_y), (pad + int(w * 0.06), bar_y + 4)],
                   fill=(201, 169, 110))

    # "FRESH WORK" label
    label_y = bar_y + int(h * 0.025)
    draw.text((pad, label_y), "FRESH WORK",
              font=f_label, fill=(201, 169, 110))

    # Service — large
    lines  = _wrap_text(service, f_service, split_x - pad * 2, draw)
    svc_y  = label_y + int(h * 0.06)
    lh     = int(w * 0.052)
    for i, line in enumerate(lines[:4]):
        draw.text((pad, svc_y + i * lh),
                  line, font=f_service, fill=(255, 255, 255))

    # Handle bottom
    handle_y = h - int(h * 0.06)
    draw.text((pad, handle_y),
              f"@{ig_handle}", font=f_handle, fill=(160, 160, 160))

    return canvas


# ── Template registry ──────────────────────────────────
TEMPLATES = {
    'stacked':      tpl_stacked,
    'editorial':    tpl_editorial,
    'coral':        tpl_coral,
    'dark_minimal': tpl_dark_minimal,
    'split':        tpl_split,
}


# ── Entry point ────────────────────────────────────────
def generate_instagram_image(photo_path, output_path, template_style,
                             service, ig_handle, fmt='story'):
    if fmt not in FORMATS:
        fmt = 'story'

    tpl_fn = TEMPLATES.get(template_style, tpl_stacked)
    img    = tpl_fn(
        photo_path  = photo_path,
        fmt         = fmt,
        service     = service or 'Fresh work',
        ig_handle   = (ig_handle or 'stylebook').lstrip('@'),
    )
    img.save(output_path, 'PNG', compress_level=1)
    return output_path