from django.contrib import admin
from .models import MasterProfile, WorkExperience, Certificate, Honor


# Inlines — show experiences/certs/honors inside MasterProfile admin page

class WorkExperienceInline(admin.TabularInline):
    model = WorkExperience
    extra = 0
    fields = ('title', 'studio_name', 'city',
              'start_month', 'start_year',
              'end_month', 'end_year', 'is_current')


class CertificateInline(admin.TabularInline):
    model = Certificate
    extra = 0
    fields = ('name', 'institution', 'year', 'file_url')


class HonorInline(admin.TabularInline):
    model = Honor
    extra = 0
    fields = ('title', 'issuer', 'year')


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display    = ('user', 'specialty', 'location', 'years_exp', 'phone')
    list_filter     = ('specialty', 'home_visits')
    search_fields   = ('user__username', 'user__email', 'studio_name', 'location')
    inlines         = [WorkExperienceInline, CertificateInline, HonorInline]


@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display    = ('title', 'profile', 'studio_name', 'start_year', 'end_year', 'is_current')
    list_filter     = ('is_current',)
    search_fields   = ('title', 'studio_name', 'profile__user__username')


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display    = ('name', 'profile', 'institution', 'year')
    list_filter     = ('year',)
    search_fields   = ('name', 'institution', 'profile__user__username')


@admin.register(Honor)
class HonorAdmin(admin.ModelAdmin):
    list_display    = ('title', 'profile', 'issuer', 'year')
    list_filter     = ('year',)
    search_fields   = ('title', 'issuer', 'profile__user__username')