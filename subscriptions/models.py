# backend/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
import uuid

User = get_user_model()


def generate_api_key():
    return str(uuid.uuid4())


# ==================== PACK ====================
class Pack(models.Model):
    DURATION_CHOICES = [
        (0, 'Illimité'),
        (30, '30 jours'),
        (90, '90 jours'),
        (365, '1 an'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    features = models.JSONField(default=list, blank=True)
    is_best_plan = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # === NOUVEAUX CHAMPS QUOTA ===
    image_corrections_limit = models.PositiveIntegerField(
        default=0,
        help_text="Nombre d'envois d'images autorisés (0 = illimité)"
    )
    chat_questions_limit = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de questions au chatbot autorisées (0 = illimité)"
    )

    duration = models.PositiveIntegerField(
        choices=DURATION_CHOICES,
        default=30,
        help_text="Durée en jours (0 = illimité)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def subscribers_count(self):
        return self.subscriptions.filter(is_active=True).count()

    def __str__(self):
        return f"{self.name} ({self.image_corrections_limit} images, {self.chat_questions_limit} questions)"

    class Meta:
        verbose_name = "Pack Abonnement"
        verbose_name_plural = "Packs Abonnement"


# ==================== SUBSCRIPTION ====================
class Subscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    pack = models.ForeignKey(Pack, on_delete=models.CASCADE, related_name="subscriptions")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    api_key = models.CharField(max_length=100, unique=True, default=generate_api_key)

    # === QUOTAS ===
    image_corrections_remaining = models.PositiveIntegerField(default=0)
    chat_questions_remaining = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Création
            self.image_corrections_remaining = self.pack.image_corrections_limit
            self.chat_questions_remaining = self.pack.chat_questions_limit
            if self.pack.duration > 0:
                self.expires_at = timezone.now() + timezone.timedelta(days=self.pack.duration)
        super().save(*args, **kwargs)

    def deduct_image_correction(self):
        if self.image_corrections_remaining <= 0:
            raise ValueError("Quota d'envoi d'images épuisé.")
        self.image_corrections_remaining -= 1
        self.save()

    def deduct_chat_question(self):
        if self.chat_questions_remaining <= 0:
            raise ValueError("Quota de questions au chatbot épuisé.")
        self.chat_questions_remaining -= 1
        self.save()

    def is_expired(self):
        if self.pack.duration == 0:
            return False
        return self.expires_at and timezone.now() > self.expires_at

    def __str__(self):
        status = "ACTIVE" if self.is_active and not self.is_expired() else "EXPIRED"
        return f"{self.user.email} - {self.pack.name} [{status}]"

    class Meta:
        unique_together = ('user', 'pack')


# ==================== USAGE LOG (remplace ApiCall) ====================
class UsageLog(models.Model):
    ACTION_TYPES = [
        ('IMAGE_CORRECTION', 'Correction d\'image'),
        ('CHAT_QUESTION', 'Question au chatbot'),
    ]

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="usage_logs"
    )
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)  # ex: domaine, niveau, etc.

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['-timestamp'])]

    def __str__(self):
        return f"{self.action} - {self.subscription.user.email} - {self.timestamp.strftime('%d/%m %H:%M')}"