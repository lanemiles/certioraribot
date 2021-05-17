from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cases/<str:docket_number>/', views.detail, name='detail'),
    path('todays_cases/', views.todays_cases, name='todays_cases'),
    path('cases_to_consider_for_cfr/', views.cases_to_consider_for_cfr, name='cases_to_consider_for_cfr'),
    path('cases_with_cfr/', views.cases_with_cfr, name='cases_with_cfr'),
]