from django.urls import path
from . import views

urlpatterns = [
    path('portfolio/',                     views.portfolio_view,     name='portfolio'),

    # Instagram generator — form + async generate + polling
    path('instagram/',                     views.instagram_view,     name='instagram'),
    path('instagram/generate/',            views.instagram_generate, name='instagram_generate'),
    path('instagram/status/<int:job_id>/', views.instagram_status,   name='instagram_status'),

    path('profile/edit/',                  views.edit_profile,       name='profile_edit'),
    path('profile/',                       views.my_profile,         name='my_profile'),
    path('profile/<str:username>/',        views.profile_view,       name='profile'),
]