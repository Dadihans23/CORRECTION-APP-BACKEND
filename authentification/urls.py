from django.urls import path
from .views import (
    SignupRequestView, OTPVerificationView, LoginView,
    PasswordResetRequestView, PasswordResetConfirmView,
    ChangePasswordView, ProfileView
)
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'authentication'

urlpatterns = [
    path('signup/request/', SignupRequestView.as_view(), name='signup_request'),
    path('verify-otp/', OTPVerificationView.as_view(), name='verify_otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('password/reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/change/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/', ProfileView.as_view(), name='profile'),
]