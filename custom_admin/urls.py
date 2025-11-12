# custom_admin/urls.py
from django.urls import path
from . import views

app_name = 'custom_admin'

urlpatterns = [
    # ===============================================
    # DASHBOARD & STATS
    # ===============================================
    path('', views.admin_dashboard, name='dashboard'),
    path('billing/', views.admin_billing_stats, name='billing_stats'),
    path('user-stats/', views.admin_user_stats, name='user_stats'),
    path('analytics/', views.admin_analytics, name='analytics'),
    path('reports/', views.admin_reports, name='reports'),

    # ===============================================
    # UTILISATEURS
    # ===============================================
    path('users/', views.admin_users, name='users'),
    path('user-create/', views.admin_user_create, name='user_create'),
    path('user/<int:user_id>/', views.admin_user_detail, name='user_detail'),
    path('user/<int:user_id>/edit/', views.admin_user_edit, name='user_edit'),
    path('user/<int:user_id>/delete/', views.admin_user_delete, name='user_delete'),

    # ===============================================
    # PACKS
    # ===============================================
    path('packs/', views.admin_packs, name='packs'),
    path('pack/create/', views.admin_pack_create, name='pack_create'),
    path('pack/<int:pack_id>/', views.admin_pack_detail, name='pack_detail'),
    path('pack/<int:pack_id>/edit/', views.admin_pack_edit, name='pack_edit'),
    path('pack/<int:pack_id>/delete/', views.admin_pack_delete, name='pack_delete'),

    # ===============================================
    # ABONNEMENTS
    # ===============================================
    path('subscriptions/', views.admin_subscriptions, name='subscriptions'),
    path('subscription/<int:subscription_id>/', views.admin_subscription_detail, name='subscription_detail'),
    path('subscription/<int:subscription_id>/edit/', views.admin_subscription_edit, name='subscription_edit'),
    path('subscription/create/', views.admin_subscription_create, name='subscription_create'),

    # ===============================================
    # TÉLÉCHARGEMENT RAPPORTS
    # ===============================================
    path('report/download/<str:report_type>/', views.download_report, name='download_report'),
    path('reports/export-all/', views.export_all_reports, name='export_all_reports'),
    path('settings/', views.admin_settings, name='settings'),

]