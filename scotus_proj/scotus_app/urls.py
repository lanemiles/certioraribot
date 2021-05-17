from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cases/<str:docket_number>/', views.detail, name='detail'),
    path('update_cases/', views.update_cases, name='update_cases'),
    path('todays_cases/', views.todays_cases, name='todays_cases'),
    path('send_daily_email/', views.send_daily_email, name='send_daily_email'),
]