# backend/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'


urlpatterns = [
    # ... tes autres URLs
    path('create-packs/', views.PackListCreateView.as_view(), name='pack-list-create'),
]