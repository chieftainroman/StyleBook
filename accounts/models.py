from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


# Default working hours JSON — Mon-Fri 09:00-18:00, weekend closed
DEFAULT_WORKING_HOURS = {
    'mon': {'open': '09:00', 'close': '18:00', 'closed': False},
    'tue': {'open': '09:00', 'close': '18:00', 'closed': False},
    'wed': {'open': '09:00', 'close': '18:00', 'closed': False},
    'thu': {'open': '09:00', 'close': '18:00', 'closed': False},
    'fri': {'open': '09:00', 'close': '18:00', 'closed': False},
    'sat': {'open': '10:00', 'close': '16:00', 'closed': True},
    'sun': {'open': '10:00', 'close': '16:00', 'closed': True},
}


class MasterProfile(models.Model):
    SPECIALTY_CHOICES = [
        ('barber',     'Barber'),
        ('stylist',    'Hair Stylist'),
        ('nails',      'Nail Master'),
        ('makeup',     'Makeup Artist'),
        ('tattoo',     'Tattoo Artist'),
        ('lash',       'Lash Artist'),
        ('brow',       'Brow Artist'),
        ('esthetics',  'Esthetician'),
        ('massage',    'Massage Therapist'),
        ('other',      'Other'),
    ]

    user      = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # ── Existing fields ──
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, default='')
    bio       = models.TextField(default='')
    skills    = models.CharField(max_length=300, default='')
    ig_handle = models.CharField(max_length=100, default='')
    location  = models.CharField(max_length=100, default='')
    years_exp = models.IntegerField(default=0)

    # ── New: contact ──
    phone     = models.CharField(max_length=30, default='', blank=True)

    # ── New: studio / location detail ──
    studio_name        = models.CharField(max_length=150, default='', blank=True)
    years_at_location  = models.IntegerField(default=0)

    # ── New: services / pricing ──
    pricing_from       = models.DecimalField(max_digits=8, decimal_places=2,
                                             null=True, blank=True)
    travel_radius_km   = models.IntegerField(null=True, blank=True,
                                             help_text='Max km the master will travel for home visits')
    home_visits        = models.BooleanField(default=False)

    # ── New: languages — Postgres array ──
    languages          = ArrayField(
        models.CharField(max_length=40),
        default=list,
        blank=True,
        help_text='Languages spoken — list of strings'
    )

    # ── New: working hours — JSON ──
    working_hours      = models.JSONField(default=dict, blank=True)

    # ── New: photos (Cloudinary URLs) ──
    avatar_url         = models.URLField(max_length=500, default='', blank=True)
    cover_url          = models.URLField(max_length=500, default='', blank=True)

    def __str__(self):
        return f'{self.user.username} — {self.specialty}'

    def get_working_hours(self):
        """Return working_hours dict, falling back to defaults if empty."""
        return self.working_hours or DEFAULT_WORKING_HOURS

    def is_complete(self):
        """Check if mandatory profile fields are filled."""
        return all([
            self.specialty,
            self.location,
            self.years_exp > 0,
            self.bio,
            self.phone,
        ])