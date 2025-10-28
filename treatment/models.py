from django.db import models
import json
from authentification.models import CustomUser  # Remplace 'auth_app' par le nom de l'app contenant CustomUser

class ExerciseProcessing(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='exercises/')
    extracted_text = models.TextField()
    solution = models.JSONField()
    context = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Processing {self.id} for {self.user.phone_number}"
    
    
    



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
    