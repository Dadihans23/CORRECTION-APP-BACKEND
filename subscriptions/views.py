# backend/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Pack
from .serializer import PackSerializer ,  SubscriptionSerializer , TransactionSerializer
from rest_framework.permissions import IsAdminUser

from rest_framework.decorators import api_view, schema
from rest_framework.schemas import AutoSchema




# backend/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Pack, Subscription


class PackListCreateView(generics.ListCreateAPIView):
    """
    GET  : Récupère tous les packs actifs
    POST : Crée un nouveau pack (admin only)
    """
    
    queryset = Pack.objects.filter(is_active=True)
    serializer_class = PackSerializer
    permission_classes = [IsAuthenticated]    # Optionnel : admin seulement si tu veux

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            pack = serializer.save()
            return Response({
                'success': True,
                'message': 'Pack créé avec succès.',
                'data': PackSerializer(pack).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'message': 'Erreur de validation.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'count': queryset.count(),
            'data': serializer.data
        })







# backend/views.py
from .models import Pack, Subscription, Transaction, UsageLog

class SubscribeToPackView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        pack_id = request.data.get('pack_id')

        if not pack_id:
            return Response({
                'success': False,
                'message': 'pack_id est requis.'
            }, status=status.HTTP_400_BAD_REQUEST)

        new_pack = get_object_or_404(Pack, id=pack_id, is_active=True)

        # Récupérer l'abonnement actif
        current_sub = Subscription.objects.filter(
            user=user, is_active=True
        ).first()

        # Bloquer uniquement si même pack ET non expiré
        if current_sub and current_sub.pack.id == new_pack.id and not current_sub.is_expired():
            return Response({
                'success': False,
                'message': 'Vous êtes déjà abonné à ce pack.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # === CUMUL DES QUOTAS ===
        remaining_images = 0
        remaining_questions = 0
        previous_pack = None
        transaction_type = 'subscription'

        if current_sub:
            # Désactiver l'ancien
            current_sub.is_active = False
            current_sub.save()

            # Récupérer les quotas restants
            remaining_images = current_sub.image_corrections_remaining
            remaining_questions = current_sub.chat_questions_remaining
            previous_pack = current_sub.pack

            if current_sub.is_expired():
                transaction_type = 'renewal'
                action = "Renouvellement"
                message = f"Renouvellement de {new_pack.name} avec cumul des quotas restants."
            else:
                transaction_type = 'upgrade'
                action = "Upgrade"
                message = f"Upgrade réussi : {current_sub.pack.name} → {new_pack.name}"
        else:
            action = "Souscription"
            message = f"Abonnement à {new_pack.name} créé avec succès."

        # === CRÉER LA TRANSACTION ===
        Transaction.objects.create(
            user=user,
            pack=new_pack,
            previous_pack=previous_pack,
            transaction_type=transaction_type,
            price_paid=new_pack.price,
        )

        # === NOUVEAU ABONNEMENT AVEC CUMUL ===
        subscription = Subscription(
            user=user,
            pack=new_pack,
            image_corrections_remaining=new_pack.image_corrections_limit + remaining_images,
            chat_questions_remaining=new_pack.chat_questions_limit + remaining_questions,
        )

        if new_pack.duration > 0:
            subscription.expires_at = timezone.now() + timezone.timedelta(days=new_pack.duration)

        subscription.save()

        return Response({
            'success': True,
            'action': action,
            'message': message,
            'cumulated_quotas': {
                'images_added': remaining_images,
                'questions_added': remaining_questions
            },
            'data': SubscriptionSerializer(subscription).data
        }, status=status.HTTP_201_CREATED)
    
        
class MySubscriptionView(generics.RetrieveAPIView):
    """
    GET : Récupérer l'abonnement actif de l'utilisateur
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        subscription = Subscription.objects.filter(
            user=request.user, is_active=True
        ).first()

        if not subscription or subscription.is_expired():
            return Response({
                'success': False,
                'message': 'Aucun abonnement actif.'
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'data': SubscriptionSerializer(subscription).data
        })        
        
        
# views.py
@api_view(['GET'])
def subscription_history(request):
    permission_classes = [IsAuthenticated]
    """
    GET : Historique complet des abonnements (actifs + expirés)
    """
    subscriptions = Subscription.objects.filter(
        user=request.user
    ).select_related('pack').order_by('-created_at')
    
    serializer = SubscriptionSerializer(subscriptions, many=True)
    return Response({
        'success': True,
        'count': subscriptions.count(),
        'data': serializer.data
    })
    
  
  
class SubscriptionDashboardView(generics.RetrieveAPIView):
    """
    GET : Tableau de bord complet de l'abonnement utilisateur pour l'app mobile.
    Retourne : abonnement actuel, quotas, usage, historique, stats.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        now = timezone.now()

        # === ABONNEMENT ACTIF ===
        subscription = Subscription.objects.filter(
            user=user, is_active=True
        ).select_related('pack').first()

        if not subscription:
            return Response({
                'success': True,
                'has_subscription': False,
                'subscription': None,
                'quotas': None,
                'usage': None,
                'history': None,
            })

        is_expired = subscription.is_expired()

        # === QUOTAS (total réel = remaining + utilisé, inclut les quotas cumulés) ===
        pack = subscription.pack
        images_used = UsageLog.objects.filter(subscription=subscription, action='IMAGE_CORRECTION').count()
        questions_used = UsageLog.objects.filter(subscription=subscription, action='CHAT_QUESTION').count()
        images_total = subscription.image_corrections_remaining + images_used
        questions_total = subscription.chat_questions_remaining + questions_used
        # Pourcentages basés sur le total réel
        images_pct = round(
            (subscription.image_corrections_remaining / images_total) * 100
        ) if images_total > 0 else 100
        questions_pct = round(
            (subscription.chat_questions_remaining / questions_total) * 100
        ) if questions_total > 0 else 100

        # === JOURS RESTANTS ===
        if subscription.expires_at and not is_expired:
            days_remaining = (subscription.expires_at - now).days
        elif is_expired:
            days_remaining = 0
        else:
            days_remaining = None  # Illimité

        # === USAGE RÉCENT (7 derniers jours) ===
        seven_days_ago = now - timezone.timedelta(days=7)
        recent_logs = UsageLog.objects.filter(
            subscription=subscription,
            timestamp__gte=seven_days_ago
        )
        images_this_week = recent_logs.filter(action='IMAGE_CORRECTION').count()
        questions_this_week = recent_logs.filter(action='CHAT_QUESTION').count()

        # === USAGE TOTAL sur cet abonnement ===
        all_logs = UsageLog.objects.filter(subscription=subscription)
        total_images_used = all_logs.filter(action='IMAGE_CORRECTION').count()
        total_questions_used = all_logs.filter(action='CHAT_QUESTION').count()

        # === DERNIÈRE ACTIVITÉ ===
        last_log = all_logs.first()  # Déjà ordonné par -timestamp
        last_activity = last_log.timestamp if last_log else None

        # === USAGE PAR JOUR (7 derniers jours pour graphique) ===
        daily_usage = []
        for i in range(6, -1, -1):
            day = (now - timezone.timedelta(days=i)).date()
            day_start = timezone.make_aware(
                timezone.datetime.combine(day, timezone.datetime.min.time())
            )
            day_end = day_start + timezone.timedelta(days=1)
            day_logs = recent_logs.filter(timestamp__gte=day_start, timestamp__lt=day_end)
            daily_usage.append({
                'date': day.isoformat(),
                'corrections': day_logs.filter(action='IMAGE_CORRECTION').count(),
                'questions': day_logs.filter(action='CHAT_QUESTION').count(),
            })

        # === HISTORIQUE DES ABONNEMENTS ===
        past_subscriptions = Subscription.objects.filter(
            user=user, is_active=False
        ).select_related('pack').order_by('-created_at')[:5]

        past_subs_data = [{
            'pack_name': sub.pack.name,
            'created_at': sub.created_at,
            'expires_at': sub.expires_at,
            'duration_days': sub.pack.duration,
        } for sub in past_subscriptions]

        # === DERNIÈRE TRANSACTION ===
        last_transaction = Transaction.objects.filter(user=user).first()
        last_transaction_data = None
        if last_transaction:
            last_transaction_data = {
                'type': last_transaction.get_transaction_type_display(),
                'pack_name': last_transaction.pack.name,
                'price_paid': str(last_transaction.price_paid),
                'date': last_transaction.created_at,
            }

        return Response({
            'success': True,
            'has_subscription': True,
            'subscription': {
                'id': subscription.id,
                'pack_name': pack.name,
                'pack_slug': pack.slug,
                'pack_price': str(pack.price),
                'pack_description': pack.description,
                'pack_features': pack.features,
                'is_active': subscription.is_active,
                'is_expired': is_expired,
                'created_at': subscription.created_at,
                'expires_at': subscription.expires_at,
                'days_remaining': days_remaining,
            },
            'quotas': {
                'images': {
                    'remaining': subscription.image_corrections_remaining,
                    'total': images_total,
                    'used': images_used,
                    'pack_limit': pack.image_corrections_limit,
                    'percentage_remaining': images_pct,
                },
                'questions': {
                    'remaining': subscription.chat_questions_remaining,
                    'total': questions_total,
                    'used': questions_used,
                    'pack_limit': pack.chat_questions_limit,
                    'percentage_remaining': questions_pct,
                },
            },
            'usage': {
                'total_corrections': total_images_used,
                'total_questions': total_questions_used,
                'corrections_this_week': images_this_week,
                'questions_this_week': questions_this_week,
                'last_activity': last_activity,
                'daily_usage': daily_usage,
            },
            'history': {
                'past_subscriptions': past_subs_data,
                'last_transaction': last_transaction_data,
            },
        })


class TransactionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).select_related('pack', 'previous_pack')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'count': queryset.count(),
            'data': serializer.data
        })    