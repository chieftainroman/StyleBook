from django.db import models
from django.contrib.auth.models import User


class MasterProfile(models.Model):
    SPECIALTY_CHOICES = [
        ('barber',  'Barber'),
        ('stylist', 'Hair Stylist'),
        ('nails',   'Nail Master'),
        ('makeup',  'Makeup Artist'),
        ('other',   'Other'),
    ]

    user      = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, default='')
    bio       = models.TextField(default='')
    skills    = models.CharField(max_length=300, default='')
    ig_handle = models.CharField(max_length=100, default='')
    location  = models.CharField(max_length=100, default='')
    years_exp = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.user.username} — {self.specialty}'