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
from .models import Pack, Subscription, Transaction  # ← Ajouter Transaction

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

        if current_sub and current_sub.pack.id == new_pack.id:
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