"""
Smart service presets per specialty. Masters see these as toggleable
suggestions when setting up their services, with sensible defaults.

Format: list of (name, duration_minutes, suggested_price_low, suggested_price_high)
Prices in USD; localized later.
"""

SERVICE_PRESETS = {
    'barber': [
        ('Haircut',                    30,  20, 50),
        ('Beard trim',                 15,  10, 25),
        ('Hot towel shave',            45,  30, 60),
        ('Hair + beard combo',         45,  30, 75),
        ('Buzz cut',                   15,  15, 30),
        ('Skin fade',                  45,  35, 70),
        ('Kids haircut',               20,  15, 35),
        ('Eyebrow trim',               10,   8, 20),
        ('Hair wash',                  15,   5, 20),
        ('Lineup / edge up',           15,  10, 25),
    ],
    'stylist': [
        ('Women\'s haircut',           60,  40, 100),
        ('Men\'s haircut',             30,  25, 60),
        ('Blowout & style',            45,  35, 80),
        ('Hair color (single)',        90,  60, 150),
        ('Highlights',                120,  90, 250),
        ('Balayage',                  150, 120, 300),
        ('Root touch-up',              60,  50, 100),
        ('Toner / gloss',              30,  25, 60),
        ('Wash & blowdry',             30,  25, 50),
        ('Updo / event styling',       60,  60, 150),
        ('Hair treatment / mask',      30,  25, 60),
    ],
    'nails': [
        ('Classic manicure',           30,  20, 40),
        ('Gel manicure',               45,  30, 55),
        ('Acrylic full set',           75,  45, 90),
        ('Acrylic fill',               60,  35, 65),
        ('Classic pedicure',           45,  30, 50),
        ('Gel pedicure',               60,  40, 70),
        ('Nail art (per nail)',        10,   3, 15),
        ('Nail repair',                15,   5, 15),
        ('Soak-off',                   20,  10, 25),
        ('French tips',                15,   8, 20),
    ],
    'makeup': [
        ('Day / natural makeup',       45,  50, 100),
        ('Evening glam',               60,  75, 150),
        ('Bridal makeup',              90, 150, 350),
        ('Bridal trial',               60,  80, 150),
        ('Makeup lesson',              90,  80, 200),
        ('Editorial / photoshoot',     90, 120, 300),
        ('Lashes (strip)',             15,  10, 30),
        ('Eye look only',              30,  35, 70),
    ],
    'tattoo': [
        ('Small piece (palm-size)',    60,  80, 200),
        ('Medium piece (forearm)',    120, 200, 500),
        ('Large piece (sleeve start)',240, 400, 1200),
        ('Consultation',               30,   0,  50),
        ('Touch-up',                   45,  40, 150),
        ('Cover-up consultation',      45,   0,  75),
        ('Fine line single',           45,  60, 200),
        ('Lettering / script',         60,  80, 250),
    ],
    'lash': [
        ('Classic lash extensions',    90,  70, 150),
        ('Hybrid set',                120,  90, 175),
        ('Volume set',                150, 110, 225),
        ('Mega volume',               180, 140, 275),
        ('Lash fill (2 weeks)',        60,  45,  90),
        ('Lash fill (3 weeks)',        75,  55, 110),
        ('Lash lift',                  60,  55, 110),
        ('Lash removal',               30,  20,  50),
    ],
    'brow': [
        ('Brow shaping (wax)',         20,  15, 35),
        ('Brow shaping (thread)',      20,  15, 40),
        ('Brow tint',                  20,  20, 40),
        ('Brow lamination',            45,  60, 110),
        ('Henna brows',                45,  40,  80),
        ('Microblading',              120, 300, 700),
        ('Microblading touch-up',      90, 100, 300),
        ('Brow tint + shape combo',    30,  30,  60),
    ],
    'esthetics': [
        ('Classic facial',             60,  60, 130),
        ('Deep cleansing facial',      75,  80, 160),
        ('Hydrating facial',           60,  70, 140),
        ('Anti-aging facial',          75,  90, 180),
        ('Chemical peel',              45,  80, 180),
        ('Microdermabrasion',          45,  90, 175),
        ('LED light therapy',          30,  50, 100),
        ('Extraction add-on',          15,  20,  40),
    ],
    'massage': [
        ('Swedish — 60 min',           60,  60, 130),
        ('Swedish — 90 min',           90,  90, 180),
        ('Deep tissue — 60 min',       60,  75, 150),
        ('Deep tissue — 90 min',       90, 110, 200),
        ('Sports massage',             60,  80, 160),
        ('Prenatal massage',           60,  80, 160),
        ('Hot stone massage',          75,  90, 180),
        ('Couples massage',            60, 140, 280),
    ],
    'other': [
        ('Standard session',           60,  40, 100),
        ('Short session',              30,  25,  60),
        ('Extended session',           90,  60, 150),
        ('Consultation',               30,  20,  60),
    ],
}


def get_presets_for_specialty(specialty):
    """Return preset list for a specialty, or empty list if not found."""
    return SERVICE_PRESETS.get(specialty, [])


def get_suggested_price(specialty, service_name):
    """Return midpoint of suggested price range for a service, or None."""
    presets = get_presets_for_specialty(specialty)
    for name, duration, low, high in presets:
        if name == service_name:
            return round((low + high) / 2, 2)
    return None