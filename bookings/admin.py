from django.contrib import admin
from .models import Reservation
from django.contrib import admin
from .models import Booking, OTPRequest


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display    = ['reference_code', 'master', 'service', 'client_name',
                       'start_time', 'status', 'source', 'created_at']
    list_filter     = ['status', 'source', 'first_time_client']
    search_fields   = ['reference_code', 'client_name', 'client_email',
                       'master__user__username']
    readonly_fields = ['reference_code', 'created_at', 'updated_at',
                       'cancelled_at', 'reminder_sent_at']
    date_hierarchy  = 'start_time'


@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display    = ['code', 'booking', 'client_email', 'attempts',
                       'verified_at', 'expires_at', 'created_at']
    list_filter     = ['verified_at']
    search_fields   = ['code', 'client_email', 'booking__reference_code']
    readonly_fields = ['created_at']

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display  = ['client_name', 'service', 'date', 'time', 'status', 'user']
    list_filter   = ['status', 'service']
    search_fields = ['client_name']
    date_hierarchy = None