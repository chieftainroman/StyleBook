from django.urls import path
from . import views

urlpatterns = [
    path('register/',   views.register_view,   name='register'),
    path('login/',      views.login_view,       name='login'),
    path('logout/',     views.logout_view,      name='logout'),
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email,           name='verify_email'),
    path('resend-verification/',                   views.resend_verification,    name='resend_verification'),
    path('forgot-password/',                       views.forgot_password,        name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/', views.reset_password,       name='reset_password'),
]