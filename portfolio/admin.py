from django.contrib import admin
from .models import PortfolioItem


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display  = ['service', 'client_name', 'category', 'template_style', 'date', 'user']
    list_filter   = ['category', 'template_style']
    search_fields = ['client_name', 'service']