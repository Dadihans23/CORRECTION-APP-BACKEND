from django.urls import path
from .views import ProcessImageView , HistoryView

urlpatterns = [
    path('process-image/', ProcessImageView.as_view(), name='process-image'),
    # Tes autres endpoints auth (login, profile, etc.)
    path('history/', HistoryView.as_view(), name='hystory'),

]