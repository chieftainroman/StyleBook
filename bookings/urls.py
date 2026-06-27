from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                          views.dashboard_view, name='dashboard'),
    path('reservations/',                       views.dashboard_view, name='reservations'),
    path('reservations/<int:res_id>/complete/', views.dashboard_view, name='complete_reservation'),
    path('reservations/<int:res_id>/delete/',   views.dashboard_view, name='delete_reservation'),
    path('book/<str:username>/',                    views.book_master,              name='book_master'),
    path('book/<str:username>/api/availability/',   views.availability_api,         name='availability_api'),
    path('book/<str:username>/api/summary/',        views.availability_summary_api, name='availability_summary_api'),
]