from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, OTPCode, PendingUser
from django.contrib.auth.hashers import make_password

# class CustomUserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomUser
#         fields = ['id', 'phone_number', 'email', 'first_name', 'last_name', 'is_verified']
        
        
        
class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'is_verified', 'country', 'school_level', 'institution', 'age']
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False},
            'is_verified': {'read_only': True},
            'country': {'required': False},
            'school_level': {'required': False},
            'institution': {'required': False},
            'age': {'required': False}
        }        
        

class SignupRequestSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = PendingUser
        fields = ['phone_number', 'email', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        return PendingUser.objects.create(**validated_data)

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)
    code = serializers.CharField(max_length=6, required=True)
    purpose = serializers.ChoiceField(choices=['signup', 'reset'], required=True)

class PasswordResetRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)

class PasswordResetConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)
    code = serializers.CharField(max_length=6, required=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'min_length': {"message": "Le mot de passe doit contenir au moins 8 caractères."}
        }
    )

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'min_length': {"message": "Le nouveau mot de passe doit contenir au moins 8 caractères."}
        }
    )