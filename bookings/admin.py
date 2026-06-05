from django.contrib import admin
from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display  = ['client_name', 'service', 'date', 'time', 'status', 'user']
    list_filter   = ['status', 'service']
    search_fields = ['client_name']
    date_hierarchy = None