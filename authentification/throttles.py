from rest_framework.throttling import AnonRateThrottle


class SignupRateThrottle(AnonRateThrottle):
    """5 tentatives d'inscription par minute par IP."""
    scope = 'signup'


class OTPRateThrottle(AnonRateThrottle):
    """5 vérifications OTP par minute par IP."""
    scope = 'otp'


class LoginRateThrottle(AnonRateThrottle):
    """10 tentatives de connexion par minute par IP."""
    scope = 'login'


class PasswordResetRateThrottle(AnonRateThrottle):
    """5 demandes de reset par minute par IP."""
    scope = 'password_reset'
