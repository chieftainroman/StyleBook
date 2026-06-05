from django.contrib import admin
from .models import MasterProfile


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'specialty', 'ig_handle', 'location']
    list_filter   = ['specialty']
    search_fields = ['user__username', 'user__email']