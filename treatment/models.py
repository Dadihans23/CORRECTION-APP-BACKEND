from django.db import models
import json
from authentification.models import CustomUser  # Remplace 'auth_app' par le nom de l'app contenant CustomUser

# backend/models.py
from django.db import models
from django.utils import timezone

# backend/models.py
from django.db import models
from django.utils import timezone
import uuid



class CorrectionHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='corrections')
    user_domain = models.CharField(max_length=100, default='Mathématiques')
    user_level = models.CharField(max_length=100, default='Collège (6ᵉ – 3ᵉ)')
    user_exercise_type = models.CharField(max_length=100, default='Problème à résoudre')
    user_expectation = models.CharField(max_length=100, default='Solution étape par étape')
    user_info = models.TextField(blank=True, default='')
    detected_branch = models.CharField(max_length=50, default='Général')
    detected_branch_explanation = models.TextField(blank=True)
    domain_mismatch = models.TextField(blank=True, null=True)
    response_datetime = models.CharField(max_length=50)
    extracted_text = models.TextField(blank=True)
    solution = models.JSONField(null=True, blank=True)  # Pour stocker result et steps
    content_type = models.CharField(max_length=50, default='GENERAL')
    educational_mode = models.BooleanField(default=False)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Historique de correction'
        verbose_name_plural = 'Historiques de correction'

    def __str__(self):
        return f"Correction {self.id} by {self.user.phone_number} at {self.created_at}"
    



class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.title and self.messages.exists():
            first_msg = self.messages.filter(role='user').first()
            if first_msg:
                self.title = first_msg.content[:50] + ("..." if len(first_msg.content) > 50 else "")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or "Nouvelle conversation"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'Utilisateur'),
        ('model', 'IA'),
    )

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages' , null=True,  blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    gemini_response_time = models.FloatField(null=True, blank=True)  # en ms

    class Meta:
        ordering = ['created_at']
        
        
        
class ImageCorrection(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='image_corrections')
    image = models.ImageField(upload_to='corrections/%Y/%m/%d/')
    domaine = models.CharField(max_length=100, default='Mathématiques')
    niveau = models.CharField(max_length=100, default='Collège')
    type_exercice = models.CharField(max_length=100, default='Problème')
    attente = models.CharField(max_length=100, default='Étape par étape')
    infos_complementaires = models.TextField(blank=True)

    # Résultat Gemini
    correction_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Correction Photo"
        verbose_name_plural = "Corrections Photo"

    def __str__(self):
        return f"{self.domaine} - {self.niveau} - {self.created_at.strftime('%d/%m %H:%M')}"        