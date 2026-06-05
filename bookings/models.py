from django.db import models
from django.contrib.auth.models import User


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