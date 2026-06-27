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
    # ── Booking configuration ──
    min_lead_time_hours = models.PositiveSmallIntegerField(
        default=2,
        help_text='Minimum hours between booking time and appointment',
    )
    concurrent_clients = models.PositiveSmallIntegerField(
        default=1,
        help_text='Number of clients you can handle simultaneously',
    )
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
    # ── Onboarding state ──
    onboarding_completed = models.BooleanField(default=False,
                                               help_text='True once the user has finished or explicitly skipped the wizard')
    # ── Email verification ──
    email_verified = models.BooleanField(default=False)
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
        
        
        
# ════════════════════════════════════════════════
# WorkExperience — timeline of a master's job history
# ════════════════════════════════════════════════

class WorkExperience(models.Model):
    profile      = models.ForeignKey(MasterProfile, on_delete=models.CASCADE,
                                     related_name='experiences')
    title        = models.CharField(max_length=120,
                                    help_text='e.g. "Senior Barber"')
    studio_name  = models.CharField(max_length=150, blank=True, default='',
                                    help_text='e.g. "Iron & Comb Barbershop"')
    city         = models.CharField(max_length=100, blank=True, default='')

    # ── Dates: month + year only, no day. Stored as 1st of month for sorting. ──
    start_month  = models.IntegerField()       # 1-12
    start_year   = models.IntegerField()       # e.g. 2022
    end_month    = models.IntegerField(null=True, blank=True)
    end_year     = models.IntegerField(null=True, blank=True)
    is_current   = models.BooleanField(default=False,
                                       help_text='I currently work here')

    description  = models.TextField(blank=True, default='')

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_current', '-end_year', '-end_month',
                    '-start_year', '-start_month']

    def __str__(self):
        return f'{self.title} @ {self.studio_name or "—"}'

    def period_display(self):
        """Human-readable date range: 'Jan 2022 – Present' or 'Jan 2022 – Mar 2025'."""
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        start = f'{months[self.start_month]} {self.start_year}'
        if self.is_current:
            return f'{start} – Present'
        if self.end_month and self.end_year:
            end = f'{months[self.end_month]} {self.end_year}'
            return f'{start} – {end}'
        return start


# ════════════════════════════════════════════════
# Certificate — formal training / qualification documents
# ════════════════════════════════════════════════

class Certificate(models.Model):
    profile      = models.ForeignKey(MasterProfile, on_delete=models.CASCADE,
                                     related_name='certificates')
    name         = models.CharField(max_length=200,
                                    help_text='e.g. "Master Barber Diploma"')
    institution  = models.CharField(max_length=200,
                                    help_text='e.g. "NY Barber Academy"')
    year         = models.IntegerField()

    # ── File hosted on Cloudinary (PDF or image) ──
    file_url     = models.URLField(max_length=500, blank=True, default='',
                                   help_text='Cloudinary URL of the cert scan')
    file_kind    = models.CharField(max_length=10, blank=True, default='',
                                    help_text='"image" or "pdf"')

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-created_at']

    def __str__(self):
        return f'{self.name} ({self.year})'


# ════════════════════════════════════════════════
# Honor — awards, recognition, achievements
# ════════════════════════════════════════════════

class Honor(models.Model):
    profile      = models.ForeignKey(MasterProfile, on_delete=models.CASCADE,
                                     related_name='honors')
    title        = models.CharField(max_length=200,
                                    help_text='e.g. "Best Barber NYC 2023"')
    issuer       = models.CharField(max_length=200, blank=True, default='',
                                    help_text='e.g. "NYC Style Awards"')
    year         = models.IntegerField()

    # ── Optional image (trophy photo or certificate) ──
    image_url    = models.URLField(max_length=500, blank=True, default='')

    description  = models.TextField(blank=True, default='')

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-created_at']

    def __str__(self):
        return f'{self.title} ({self.year})'
    
    
class Service(models.Model):
    """A service a master offers to clients."""

    profile = models.ForeignKey(
        MasterProfile,
        on_delete=models.CASCADE,
        related_name='services',
    )

    name             = models.CharField(max_length=100)
    duration_minutes = models.PositiveSmallIntegerField(
        help_text='How long this service takes (minutes)',
    )
    price            = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Price in your local currency',
    )
    description      = models.TextField(blank=True)
    photo_url        = models.URLField(blank=True, help_text='Optional photo of this service')

    sort_order       = models.PositiveSmallIntegerField(default=0)
    is_active        = models.BooleanField(default=True,
                                           help_text='Inactive services are hidden from clients')

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f'{self.name} ({self.duration_minutes}min · ${self.price})'

    def duration_display(self):
        """Human-readable duration: '45 min' or '1h 30min'."""
        h, m = divmod(self.duration_minutes, 60)
        if h and m:
            return f'{h}h {m}min'
        if h:
            return f'{h}h'
        return f'{m}min'
    
    
class UnavailableSlot(models.Model):
    """
    Master-marked times when they are NOT available for bookings,
    even within their normal working hours.
    Single occurrence OR recurring weekly.
    """

    profile = models.ForeignKey(
        MasterProfile,
        on_delete=models.CASCADE,
        related_name='unavailable_slots',
    )

    # ── For single occurrences ──
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime   = models.DateTimeField(null=True, blank=True)

    # ── For recurring weekly blocks ──
    is_recurring   = models.BooleanField(default=False)
    weekday        = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='0=Monday, 6=Sunday — only for recurring blocks',
    )
    start_time     = models.TimeField(null=True, blank=True,
                                      help_text='Only for recurring blocks')
    end_time       = models.TimeField(null=True, blank=True,
                                      help_text='Only for recurring blocks')

    # ── Metadata ──
    reason         = models.CharField(max_length=200, blank=True,
                                      help_text='Optional internal note: "Personal", "Vacation", etc.')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_datetime', 'weekday', 'start_time']

    def __str__(self):
        if self.is_recurring:
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            day = days[self.weekday] if self.weekday is not None else '?'
            return f'Every {day} {self.start_time}-{self.end_time}'
        return f'{self.start_datetime} → {self.end_datetime}'

    def clean(self):
        """Validate that the right fields are set for the slot type."""
        from django.core.exceptions import ValidationError

        if self.is_recurring:
            if self.weekday is None or not self.start_time or not self.end_time:
                raise ValidationError(
                    'Recurring slots require weekday, start_time, and end_time.'
                )
            if self.start_time >= self.end_time:
                raise ValidationError('End time must be after start time.')
        else:
            if not self.start_datetime or not self.end_datetime:
                raise ValidationError(
                    'Single-occurrence slots require start_datetime and end_datetime.'
                )
            if self.start_datetime >= self.end_datetime:
                raise ValidationError('End must be after start.')