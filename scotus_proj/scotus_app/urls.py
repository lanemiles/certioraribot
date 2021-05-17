from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cases/<str:docket_number>/', views.detail, name='detail'),
    path('todays_cases/', views.todays_cases, name='todays_cases'),
    path('consider_for_cfr_cases/', views.consider_for_cfr_cases, name='consider_for_cfr_cases'),
    path('has_cfr_cases/', views.has_cfr_cases, name='has_cfr_cases'),
]