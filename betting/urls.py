# Andrija Trnavcevic 2023/0242

from django.urls import path

from . import views

app_name = 'betting'

urlpatterns = [
    path('history/', views.vote_history, name='vote_history'),
]
