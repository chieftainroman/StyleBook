from django.urls import path
from . import views

urlpatterns = [
    path('portfolio/',                  views.portfolio_view,      name='portfolio'),
    path('profile/edit/', views.edit_profile, name='profile_edit'),
    # Instagram generator
    path('instagram/',                  views.instagram_view,      name='instagram'),
    path('instagram/generate/',         views.instagram_generate,  name='instagram_generate'),
    path('instagram/status/<int:job_id>/', views.instagram_status, name='instagram_status'),

    # Template thumbnail proxy (cached redirect to Placid CDN)
    path('instagram/thumbnail/<str:template_id>/', views.template_thumbnail,
         name='template_thumbnail'),

    path('profile/edit/',               views.edit_profile,        name='profile_edit'),
path('profile/upload-avatar/',      views.upload_avatar,         name='upload_avatar'),
    path('profile/upload-cover/',       views.upload_cover,          name='upload_cover'),
    path('profile/upload-cert-file/',   views.upload_certificate_file, name='upload_cert_file'),
    path('profile/upload-honor-image/', views.upload_honor_image,    name='upload_honor_image'),
    path('profile/',                    views.my_profile,          name='my_profile'),
    path('profile/<str:username>/',     views.profile_view,        name='profile'),
]