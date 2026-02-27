# backend/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'


urlpatterns = [
    path('create-packs/', views.PackListCreateView.as_view(), name='pack-list-create'),
    path('subscribe/', views.SubscribeToPackView.as_view(), name='subscribe'),
    path('my-subscription/', views.MySubscriptionView.as_view(), name='my-subscription'),
    path('subscription-history/', views.subscription_history, name='subscription-history'),
    path('transactions/', views.TransactionListView.as_view(), name='transactions'),
    path('dashboard/', views.SubscriptionDashboardView.as_view(), name='subscription-dashboard'),
    # === PAIEMENT GENIUSPAY ===
    path('payment/webhook/', views.geniuspay_webhook, name='payment-webhook'),
    path('payment/status/<str:token_pay>/', views.check_payment_status, name='payment-status'),
    path('payment/cancel/<str:token_pay>/', views.cancel_payment, name='payment-cancel'),
]