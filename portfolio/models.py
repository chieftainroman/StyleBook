from django.db import models
from django.contrib.auth.models import User


class PortfolioItem(models.Model):
    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_items')
    reservation_id = models.IntegerField(null=True, blank=True)
    client_name    = models.CharField(max_length=100, default='')
    service        = models.CharField(max_length=200)
    category       = models.CharField(max_length=50, default='')
    image          = models.CharField(max_length=300)          # filename in uploads/
    generated_image= models.CharField(max_length=300, default='') # filename in generated/
    template_style = models.CharField(max_length=50, default='')
    caption        = models.TextField(default='')
    hashtags       = models.CharField(max_length=500, default='')
    date           = models.CharField(max_length=20, default='')
    fmt = models.CharField(max_length=20, default='story') 
    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f'{self.service} — {self.client_name}'