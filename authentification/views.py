from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import (
    SignupRequestSerializer, OTPVerificationSerializer, LoginSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ChangePasswordSerializer, CustomUserSerializer
)
from .models import CustomUser, OTPCode, PendingUser
from .throttles import SignupRateThrottle, OTPRateThrottle, LoginRateThrottle, PasswordResetRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate
from django.db import IntegrityError
import re
import logging

logger = logging.getLogger(__name__)

class SignupRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SignupRateThrottle]

    def post(self, request):
        serializer = SignupRequestSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['phone_number', 'email', 'password', 'non_field_errors'] if field in errors), "Une erreur s'est produite.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        email = serializer.validated_data.get('email')
        # Validation du format E.164
        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Le numéro de téléphone doit être au format E.164 (ex. : +33123456789)."}, status=status.HTTP_400_BAD_REQUEST)
        # Vérification de l'unicité
        if CustomUser.objects.filter(phone_number=phone_number).exists() or PendingUser.objects.filter(phone_number=phone_number).exists():
            return Response({"message": "Ce numéro de téléphone est déjà utilisé."}, status=status.HTTP_400_BAD_REQUEST)
        if email and CustomUser.objects.filter(email=email).exists():
            return Response({"message": "Un utilisateur avec cet email existe déjà."}, status=status.HTTP_400_BAD_REQUEST)

        pending_user = serializer.save()
        otp = OTPCode.objects.create(pending_user=pending_user, purpose='signup')
       

        return Response({"message": "Code OTP envoyé. Vérifiez votre numéro de téléphone."}, status=status.HTTP_200_OK)

class OTPVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['phone_number', 'code', 'purpose', 'non_field_errors'] if field in errors), "Une erreur s'est produite.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']
        purpose = serializer.validated_data['purpose']

        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Le numéro de téléphone doit être au format E.164 (ex. : +33123456789)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if purpose == 'signup':
                try:
                    pending_user = PendingUser.objects.get(phone_number=phone_number)
                except PendingUser.DoesNotExist:
                    return Response(
                        {"message": "Numéro introuvable. Veuillez recommencer l'inscription."},
                        status=status.HTTP_404_NOT_FOUND
                    )
                # Vérifier que la demande d'inscription n'a pas expiré (10 min)
                if not pending_user.is_valid():
                    pending_user.delete()
                    return Response(
                        {"message": "Votre demande d'inscription a expiré. Veuillez recommencer l'inscription."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                try:
                    otp = OTPCode.objects.filter(pending_user=pending_user, code=code, purpose=purpose).latest('created_at')
                except OTPCode.DoesNotExist:
                    return Response({"message": "Code OTP incorrect."}, status=status.HTTP_400_BAD_REQUEST)
                if not otp.is_valid():
                    otp.delete()
                    return Response({"message": "Code OTP expiré. Utilisez 'Renvoyer le code' pour en obtenir un nouveau."}, status=status.HTTP_400_BAD_REQUEST)
                user = CustomUser.objects.create_user(
                    phone_number=pending_user.phone_number,
                    email=pending_user.email,
                    first_name=pending_user.first_name,
                    last_name=pending_user.last_name,
                    password=pending_user.password,
                    role=pending_user.role,
                    is_active=True,
                    is_verified=True
                )
                pending_user.delete()
                otp.delete()
                return Response({"message": "Inscription réussie. Vous pouvez maintenant vous connecter."}, status=status.HTTP_201_CREATED)
            else:
                try:
                    user = CustomUser.objects.get(phone_number=phone_number)
                except CustomUser.DoesNotExist:
                    return Response({"message": "Numéro de téléphone introuvable."}, status=status.HTTP_404_NOT_FOUND)
                try:
                    otp = OTPCode.objects.filter(user=user, code=code, purpose=purpose).latest('created_at')
                except OTPCode.DoesNotExist:
                    return Response({"message": "Code OTP incorrect."}, status=status.HTTP_400_BAD_REQUEST)
                if not otp.is_valid():
                    otp.delete()
                    return Response({"message": "Code OTP expiré. Utilisez 'Renvoyer le code' pour en obtenir un nouveau."}, status=status.HTTP_400_BAD_REQUEST)
                otp.delete()
                return Response({"message": "Code OTP validé. Vous pouvez réinitialiser votre mot de passe."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"message": "Une erreur inattendue s'est produite."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['phone_number', 'password', 'non_field_errors'] if field in errors), "Une erreur s'est produite lors de la connexion.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        password = serializer.validated_data['password']

        # Validation du format E.164
        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Le numéro de téléphone doit être au format E.164 (ex. : +33123456789)."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérification de l'existence de l'utilisateur
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return Response({"message": "Aucun utilisateur avec ce numéro de téléphone n'existe."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request=request, phone_number=phone_number, password=password)
        if user is None:
            return Response({"message": "Mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['phone_number', 'non_field_errors'] if field in errors), "Une erreur s'est produite.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Le numéro de téléphone doit être au format E.164 (ex. : +33123456789)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            otp = OTPCode.objects.create(user=user, purpose='reset')
            return Response({"message": "Code OTP envoyé pour réinitialisation."}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response({"message": "Aucun utilisateur avec ce numéro de téléphone."}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['phone_number', 'code', 'password', 'non_field_errors'] if field in errors), "Une erreur s'est produite.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']
        password = serializer.validated_data['password']

        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Le numéro de téléphone doit être au format E.164 (ex. : +33123456789)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            reset_code = OTPCode.objects.filter(user=user, code=code, purpose='reset').latest('created_at')
            if not reset_code.is_valid():
                reset_code.delete()
                return Response({"message": "Code OTP expiré."}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(password)
            user.save()
            reset_code.delete()
            return Response({"message": "Mot de passe réinitialisé avec succès."}, status=status.HTTP_200_OK)
        except (CustomUser.DoesNotExist, OTPCode.DoesNotExist):
            return Response({"message": "Numéro de téléphone ou code OTP invalide."}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = next((errors[field][0] if isinstance(errors[field], list) else errors[field] for field in ['old_password', 'new_password', 'non_field_errors'] if field in errors), "Une erreur s'est produite.")
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        user = request.user
        if not user.check_password(old_password):
            return Response({"message": "L'ancien mot de passe est incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        if old_password == new_password:
            return Response({"message": "Le nouveau mot de passe doit être différent de l'ancien."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Mot de passe changé avec succès."}, status=status.HTTP_200_OK)





class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {"message": "Le refresh token est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Déconnexion réussie."}, status=status.HTTP_200_OK)
        except TokenError:
            return Response(
                {"message": "Token invalide ou déjà expiré."},
                status=status.HTTP_400_BAD_REQUEST
            )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = CustomUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except IntegrityError:
                return Response(
                    {"message": "Ce numéro de téléphone est déjà utilisé par un autre compte."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    """Renvoie un nouveau code OTP (signup ou reset). Utile si le SMS n'est pas arrivé."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        phone_number = request.data.get('phone_number', '').strip()
        purpose = request.data.get('purpose', 'signup')

        if not phone_number:
            return Response({"message": "Numéro de téléphone requis."}, status=status.HTTP_400_BAD_REQUEST)
        if not re.match(r'^\+\d{10,15}$', phone_number):
            return Response({"message": "Format E.164 requis (ex: +2250701234567)."}, status=status.HTTP_400_BAD_REQUEST)
        if purpose not in ('signup', 'reset'):
            return Response({"message": "Purpose invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if purpose == 'signup':
            try:
                pending_user = PendingUser.objects.get(phone_number=phone_number)
                if not pending_user.is_valid():
                    pending_user.delete()
                    return Response(
                        {"message": "Demande expirée. Veuillez recommencer l'inscription."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                OTPCode.objects.filter(pending_user=pending_user, purpose='signup').delete()
                OTPCode.objects.create(pending_user=pending_user, purpose='signup')
                return Response({"message": "Nouveau code OTP envoyé."}, status=status.HTTP_200_OK)
            except PendingUser.DoesNotExist:
                return Response({"message": "Numéro non trouvé. Veuillez recommencer l'inscription."}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                OTPCode.objects.filter(user=user, purpose='reset').delete()
                OTPCode.objects.create(user=user, purpose='reset')
                return Response({"message": "Nouveau code OTP envoyé."}, status=status.HTTP_200_OK)
            except CustomUser.DoesNotExist:
                return Response({"message": "Numéro de téléphone introuvable."}, status=status.HTTP_404_NOT_FOUND)


class UpdateFCMTokenView(APIView):
    """Enregistre ou met à jour le token FCM Firebase de l'appareil de l'utilisateur."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token', '').strip()
        if not fcm_token:
            return Response({"message": "fcm_token requis."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.fcm_token = fcm_token
        request.user.save(update_fields=['fcm_token'])
        return Response({"message": "Token FCM enregistré."}, status=status.HTTP_200_OK)