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
    path('profile/upload-avatar/',          views.upload_avatar,           name='upload_avatar'),
    path('profile/upload-cover/',           views.upload_cover,            name='upload_cover'),
    path('profile/upload-cert-file/',       views.upload_certificate_file, name='upload_cert_file'),
    path('profile/upload-honor-image/',     views.upload_honor_image,      name='upload_honor_image'),

    path('profile/experience/add/',             views.experience_add,     name='experience_add'),
    path('profile/experience/<int:pk>/edit/',   views.experience_edit,    name='experience_edit'),
    path('profile/experience/<int:pk>/delete/', views.experience_delete,  name='experience_delete'),

    path('profile/certificate/add/',             views.certificate_add,    name='certificate_add'),
    path('profile/certificate/<int:pk>/edit/',   views.certificate_edit,   name='certificate_edit'),
    path('profile/certificate/<int:pk>/delete/', views.certificate_delete, name='certificate_delete'),

    path('profile/honor/add/',             views.honor_add,    name='honor_add'),
    path('profile/honor/<int:pk>/edit/',   views.honor_edit,   name='honor_edit'),
    path('profile/honor/<int:pk>/delete/', views.honor_delete, name='honor_delete'),
    path('profile/',                    views.my_profile,          name='my_profile'),
    path('profile/<str:username>/',     views.profile_view,        name='profile'),
    # ── Services CRUD ──────────────────────────────
    path('profile/service/add/',               views.service_add,           name='service_add'),
    path('profile/service/<int:pk>/edit/',     views.service_edit,          name='service_edit'),
    path('profile/service/<int:pk>/delete/',   views.service_delete,        name='service_delete'),
    path('profile/service/<int:pk>/toggle/',   views.service_toggle_active, name='service_toggle_active'),
    path('profile/service/reorder/',           views.service_reorder,       name='service_reorder'),
    path('profile/service/upload-photo/',      views.upload_service_photo,  name='upload_service_photo'),
    path('profile/service/presets/',           views.service_presets_api,   name='service_presets_api'),
]