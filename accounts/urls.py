# Andrija Trnavcevic 2023/0242

from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('password-reset/', views.password_reset, name='password_reset'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('arbitrator-applications/', views.arbitrator_applications, name='arbitrator_applications'),
    path(
        'arbitrator-applications/<int:application_id>/approve/',
        views.approve_arbitrator_application,
        name='approve_arbitrator_application',
    ),
    path(
        'arbitrator-applications/<int:application_id>/reject/',
        views.reject_arbitrator_application,
        name='reject_arbitrator_application',
    ),
]
