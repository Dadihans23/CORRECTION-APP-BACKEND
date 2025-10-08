from django.db import models
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