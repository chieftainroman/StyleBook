from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                          views.dashboard,             name='dashboard'),
    path('reservations/',                       views.reservations_view,     name='reservations'),
    path('reservations/<int:res_id>/complete/', views.complete_reservation,  name='complete_reservation'),
    path('reservations/<int:res_id>/delete/',   views.delete_reservation,    name='delete_reservation'),
]