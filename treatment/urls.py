from django.urls import path
from .views import (
    ProcessImageView, HistoryView, user_stats,
    ChatSessionDetailView, ChatSessionListCreateView, ChatMessageCreateView,
    test_local_and_save, history_corrections, correct_and_upload, site_settings_view,
    list_support_tickets, create_support_ticket, get_support_ticket, reply_support_ticket,
)

urlpatterns = [
    path('process-image/', ProcessImageView.as_view(), name='process-image'),
    path('history/', HistoryView.as_view(), name='history'),
    path('chat/sessions/', ChatSessionListCreateView.as_view(), name='chat-sessions'),
    path('chat/sessions/<uuid:pk>/', ChatSessionDetailView.as_view(), name='chat-session-detail'),
    path('chat/message/', ChatMessageCreateView.as_view(), name='chat-message'),
    path('test/local-image/', test_local_and_save),
    path('test/production-image/', correct_and_upload),
    path('test/history/', history_corrections),
    path('user/stats/', user_stats),
    path('site-settings/', site_settings_view, name='api-site-settings'),
    # === SUPPORT TICKETS ===
    path('support/tickets/', list_support_tickets, name='support-list'),
    path('support/tickets/create/', create_support_ticket, name='support-create'),
    path('support/tickets/<int:ticket_id>/', get_support_ticket, name='support-detail'),
    path('support/tickets/<int:ticket_id>/reply/', reply_support_ticket, name='support-reply'),
]
