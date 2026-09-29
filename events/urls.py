from django.urls import path

from . import views, views_closing, views_creation

app_name = 'events'

urlpatterns = [
    path('feed/', views.feed, name='feed'),
    path('interests/', views.interests, name='interests'),

    path('create/', views_creation.create_event, name='create_event'),
    path('create/refresh/', views_creation.refresh_suggestions, name='refresh_suggestions'),
    path('create/manual/', views_creation.event_form, name='event_form_manual'),
    path('create/<int:suggested_id>/', views_creation.event_form, name='event_form_suggested'),

    path('close/', views_closing.close_queue, name='close_queue'),
    path('close/<int:event_id>/', views_closing.resolve_event, name='resolve_event'),
]
