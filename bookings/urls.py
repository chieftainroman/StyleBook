from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                          views.dashboard_view,     name='dashboard'),
path('dashboard/',                          views.dashboard_view,     name='dashboard'),
    path('reservations/',                       views.reservations_view,  name='reservations'),
    path('reservations/<str:ref>/',             views.booking_detail,     name='booking_detail'),
    path('reservations/<str:ref>/status/',      views.booking_change_status, name='booking_change_status'),
    path('reservations/<str:ref>/cancel/',      views.booking_cancel,        name='booking_cancel'),
    path('reservations/<str:ref>/notes/',       views.booking_save_notes,    name='booking_save_notes'),
    # legacy URL names — kept so any old template references don't break
    path('reservations-legacy/complete/<int:res_id>/', views.dashboard_view, name='complete_reservation'),
    path('reservations-legacy/delete/<int:res_id>/',   views.dashboard_view, name='delete_reservation'),
    path('book/<str:username>/',                  views.book_master,              name='book_master'),
    path('book/<str:username>/create/',           views.create_booking,           name='create_booking'),
    path('book/<str:username>/verify-otp/',       views.verify_otp,               name='verify_otp'),
    path('book/<str:username>/resend-otp/',       views.resend_otp,               name='resend_otp'),
    path('book/<str:username>/api/availability/', views.availability_api,         name='availability_api'),
    path('book/<str:username>/api/summary/',      views.availability_summary_api, name='availability_summary_api'),
]