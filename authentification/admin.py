from django.contrib import admin
from .models import CustomUser, PendingUser, OTPCode

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'email', 'first_name', 'last_name', 'is_active', 'is_verified')
    search_fields = ('phone_number', 'email', 'first_name', 'last_name')

@admin.register(PendingUser)
class PendingUserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'email', 'first_name', 'last_name', 'created_at', 'expires_at')
    search_fields = ('phone_number', 'email')

@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'pending_user', 'purpose', 'created_at', 'expires_at')
    search_fields = ('code', 'user__phone_number', 'pending_user__phone_number')
    list_filter = ('purpose',)