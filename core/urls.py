from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          TemplateView.as_view(template_name='index.html'), name='home'),
    path('auth/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('',          include('bookings.urls')),
    path('',          include('portfolio.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)