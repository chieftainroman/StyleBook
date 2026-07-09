from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as accounts_views
from django.views.generic import TemplateView, RedirectView

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          TemplateView.as_view(template_name='index.html'), name='home'),
    path('auth/', include('accounts.urls')),
    path('accounts/login/', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('accounts/', include('allauth.urls')),
    path('',          include('bookings.urls')),
    path('',          include('portfolio.urls')),
    path('onboarding/',                    accounts_views.onboarding_start,     name='onboarding_start'),
    path('onboarding/step/<int:step>/save/', accounts_views.onboarding_step_save, name='onboarding_step_save'),
    path('onboarding/finish/',             accounts_views.onboarding_finish,    name='onboarding_finish'),
    path('onboarding/skip/',               accounts_views.onboarding_skip,      name='onboarding_skip'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)