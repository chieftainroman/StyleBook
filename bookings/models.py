from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from accounts.models import MasterProfile, Service


class Booking(models.Model):
    """A single appointment between a client and a master."""

    STATUS_PENDING_OTP    = 'pending_otp'
    STATUS_CONFIRMED      = 'confirmed'
    STATUS_COMPLETED      = 'completed'
    STATUS_NO_SHOW        = 'no_show'
    STATUS_CANCELLED      = 'cancelled'
    STATUS_REFUSED        = 'refused'

    STATUS_CHOICES = [
        (STATUS_PENDING_OTP,  'Waiting for OTP'),
        (STATUS_CONFIRMED,    'Confirmed'),
        (STATUS_COMPLETED,    'Completed'),
        (STATUS_NO_SHOW,      'No-show'),
        (STATUS_CANCELLED,    'Cancelled'),
        (STATUS_REFUSED,      'Refused by master'),
    ]

    SOURCE_DIRECT     = 'direct_link'
    SOURCE_QR         = 'qr_code'
    SOURCE_INSTAGRAM  = 'instagram'
    SOURCE_OTHER      = 'other'

    SOURCE_CHOICES = [
        ('direct_link',  'Direct link'),
        ('profile_link', 'Profile link'),
        ('qr',           'QR code'),
        ('instagram',    'Instagram'),
        ('other',        'Other'),
    ]

    # ── Identification ──
    reference_code   = models.CharField(max_length=12, unique=True, db_index=True,
                                        help_text='Public-facing booking ID like STBK-9F4K2')

    # ── Relationships ──
    master           = models.ForeignKey(MasterProfile, on_delete=models.PROTECT,
                                         related_name='bookings')
    service          = models.ForeignKey(Service, on_delete=models.PROTECT,
                                         related_name='bookings')

    # ── Schedule ──
    start_time       = models.DateTimeField(db_index=True)
    end_time         = models.DateTimeField()

    # ── Client info (no User account required) ──
    client_name      = models.CharField(max_length=120)
    client_email     = models.EmailField()
    client_phone     = models.CharField(max_length=30, blank=True)

    # ── Notes ──
    client_notes     = models.TextField(blank=True,
                                        help_text='Client preferences or special requests')
    master_notes     = models.TextField(blank=True,
                                        help_text='Master\'s private notes — never shown to client')

    # ── Status ──
    status           = models.CharField(max_length=24, choices=STATUS_CHOICES,
                                        default=STATUS_PENDING_OTP, db_index=True)

    # ── Source tracking ──
    source           = models.CharField(max_length=24, choices=SOURCE_CHOICES,
                                        default=SOURCE_DIRECT)
    first_time_client = models.BooleanField(default=True,
                                            help_text='True if this email never booked with this master before')

    # ── Reminder tracking ──
    reminder_sent_at = models.DateTimeField(null=True, blank=True,
                                            help_text='When the 24h reminder email was sent')

    # ── Timestamps ──
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at       = models.DateTimeField(auto_now=True)
    cancelled_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['master', 'start_time']),
            models.Index(fields=['client_email']),
        ]

    def __str__(self):
        return f'{self.reference_code} — {self.client_name} → {self.master.user.username} ({self.start_time:%Y-%m-%d %H:%M})'

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = self._generate_reference_code()
        if not self.end_time and self.start_time and self.service_id:
            self.end_time = self.start_time + timezone.timedelta(
                minutes=self.service.duration_minutes
            )
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference_code():
        """Generate a unique reference code like STBK-9F4K2."""
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        # Exclude confusing characters
        alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
        for _ in range(20):
            code = 'STBK-' + ''.join(secrets.choice(alphabet) for _ in range(5))
            if not Booking.objects.filter(reference_code=code).exists():
                return code
        # Extremely unlikely fallback
        return 'STBK-' + secrets.token_hex(4).upper()

    def is_cancellable(self):
        """Can this booking still be cancelled by the client?"""
        return self.status in (self.STATUS_PENDING_OTP, self.STATUS_CONFIRMED) \
               and self.start_time > timezone.now()

    def is_reschedulable(self):
        """Can this booking still be rescheduled?"""
        return self.is_cancellable()


class OTPRequest(models.Model):
    """
    Email OTP for a pending booking. Used for verification + rate limiting.
    """
    booking         = models.ForeignKey(Booking, on_delete=models.CASCADE,
                                        related_name='otp_requests')
    code            = models.CharField(max_length=6)
    attempts        = models.PositiveSmallIntegerField(default=0)
    verified_at     = models.DateTimeField(null=True, blank=True)
    expires_at      = models.DateTimeField(db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    # For rate limiting — these are stored even after verification
    client_email    = models.EmailField(db_index=True)
    client_ip       = models.GenericIPAddressField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client_email', 'created_at']),
            models.Index(fields=['client_ip', 'created_at']),
        ]

    def __str__(self):
        verified = '✓' if self.verified_at else '✗'
        return f'OTP {self.code} for {self.booking.reference_code} {verified}'

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_locked(self):
        """5 wrong attempts = locked out."""
        return self.attempts >= 5

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('upcoming',  'Upcoming'),
        ('completed', 'Completed'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    client_name = models.CharField(max_length=100)
    date        = models.CharField(max_length=20)
    time        = models.CharField(max_length=10)
    service     = models.CharField(max_length=200)
    notes       = models.TextField(default='')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    has_portfolio = models.BooleanField(default=False)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f'{self.client_name} — {self.service} on {self.date}'
    
    @property
    def dot_color(self):
        colors = ['#F59E0B', '#34D399', '#818CF8', '#F472B6', '#60A5FA']
        return colors[self.id % 5]