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
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
import os
from django.conf import settings
import re
import logging

logger = logging.getLogger(__name__)

class SignupRequestView(APIView):
    permission_classes = [AllowAny]

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
                pending_user = PendingUser.objects.get(phone_number=phone_number)
                otp = OTPCode.objects.filter(pending_user=pending_user, code=code, purpose=purpose).latest('created_at')
                if not otp.is_valid():
                    otp.delete()
                    return Response({"message": "Code OTP expiré."}, status=status.HTTP_400_BAD_REQUEST)
                user = CustomUser.objects.create_user(
                    phone_number=pending_user.phone_number,
                    email=pending_user.email,
                    first_name=pending_user.first_name,
                    last_name=pending_user.last_name,
                    password=pending_user.password,
                    is_active=True,
                    is_verified=True
                )
                pending_user.delete()
                otp.delete()
                return Response({"message": "Inscription réussie. Vous pouvez maintenant vous connecter."}, status=status.HTTP_201_CREATED)
            else:
                user = CustomUser.objects.get(phone_number=phone_number)
                otp = OTPCode.objects.filter(user=user, code=code, purpose=purpose).latest('created_at')
                if not otp.is_valid():
                    otp.delete()
                    return Response({"message": "Code OTP expiré."}, status=status.HTTP_400_BAD_REQUEST)
                otp.delete()
                return Response({"message": "Code OTP validé. Vous pouvez réinitialiser votre mot de passe."}, status=status.HTTP_200_OK)
        except (CustomUser.DoesNotExist, PendingUser.DoesNotExist, OTPCode.DoesNotExist):
            return Response({"message": "Numéro de téléphone ou code OTP introuvable."}, status=status.HTTP_404_NOT_FOUND)

class LoginView(APIView):
    permission_classes = [AllowAny]

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

        # Authentification
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

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)

