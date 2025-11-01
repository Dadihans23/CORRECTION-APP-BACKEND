# backend/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'


urlpatterns = [
    # ... tes autres URLs
    path('create-packs/', views.PackListCreateView.as_view(), name='pack-list-create'),
    path('subscribe/', views.SubscribeToPackView.as_view(), name='subscribe'),
    path('my-subscription/', views.MySubscriptionView.as_view(), name='my-subscription'),
    path('subscription-history/', views.subscription_history, name='subscription-history'),
    path('transactions/', views.TransactionListView.as_view(), name='my-subscription'),
]