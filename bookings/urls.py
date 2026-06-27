from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('book/<str:username>/',                    views.book_master,              name='book_master'),
    path('book/<str:username>/api/availability/',   views.availability_api,         name='availability_api'),
    path('book/<str:username>/api/summary/',        views.availability_summary_api, name='availability_summary_api'),
]