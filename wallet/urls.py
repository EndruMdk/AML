from django.urls import path

from . import views

app_name = 'wallet'

urlpatterns = [
    path('', views.wallet_view, name='wallet_view'),
    path('history/', views.transaction_history, name='transaction_history'),
]
