from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cases/<str:docket_number>/', views.detail, name='detail'),
    path('todays_cases/', views.todays_cases, name='todays_cases'),
]