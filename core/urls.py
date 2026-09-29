# Andrija Trnavcevic 2023/0242

from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('stats/', views.stats, name='stats'),
    path('ban/', views.ban, name='ban'),
    path('ban/toggle/<int:user_id>/', views.toggle_ban, name='toggle_ban'),
    path('balance/', views.balance_change, name='balance_change'),
    path('balance/<int:user_id>/', views.balance_change_form, name='balance_change_form'),
    path('user-stats/', views.user_stats, name='user_stats'),
]
