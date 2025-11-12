from django.urls import path
from .views import ProcessImageView , HistoryView , user_stats , ChatSessionDetailView , ChatSessionListCreateView  , ChatSessionDetailView , ChatMessageCreateView , test_local_and_save , history_corrections , correct_and_upload , site_settings_view

urlpatterns = [
    path('process-image/', ProcessImageView.as_view(), name='process-image'),
    # Tes autres endpoints auth (login, profile, etc.)
    path('history/', HistoryView.as_view(), name='hystory'),
    path('user-stats/', user_stats, name='user_stats'),

    
    path('chat/sessions/', ChatSessionListCreateView.as_view(), name='chat-sessions'),
    path('chat/sessions/<uuid:pk>/', ChatSessionDetailView.as_view(), name='chat-session-detail'),
    path('chat/message/', ChatMessageCreateView.as_view(), name='chat-message'),
    path('test/local-image/', test_local_and_save),
    path('test/production-image/', correct_and_upload),        # ← POUR FLUTTER
    path('test/history/', history_corrections),
    path('user/stats/', user_stats),
    path('site-settings/', site_settings_view, name='api-site-settings'),





]