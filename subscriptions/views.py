# backend/views.py
import hmac
import hashlib
import uuid
import requests
from django.conf import settings
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Pack, Subscription, Transaction, UsageLog
from .serializer import PackSerializer, SubscriptionSerializer, TransactionSerializer


class PackListCreateView(generics.ListCreateAPIView):
    """
    GET  : Récupère tous les packs actifs
    POST : Crée un nouveau pack (admin only)
    """
    queryset = Pack.objects.filter(is_active=True)
    serializer_class = PackSerializer
    permission_classes = [IsAuthenticated]

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


def _geniuspay_headers():
    """Retourne les headers d'authentification GeniusPay."""
    return {
        'X-API-Key': settings.GENIUSPAY_API_KEY,
        'X-API-Secret': settings.GENIUSPAY_API_SECRET,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


class SubscribeToPackView(generics.CreateAPIView):
    """
    POST : Initie un paiement GeniusPay pour souscrire à un pack.
    Retourne une URL de paiement vers laquelle rediriger l'utilisateur.
    L'abonnement est activé uniquement après confirmation du webhook.
    """
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        pack_id = request.data.get('pack_id')
        phone_number = request.data.get('phone_number')

        if not pack_id:
            return Response({
                'success': False,
                'message': 'pack_id est requis.'
            }, status=status.HTTP_400_BAD_REQUEST)

        new_pack = get_object_or_404(Pack, id=pack_id, is_active=True)

        # Pour les packs payants, phone_number est obligatoire
        if not new_pack.is_free and not phone_number:
            return Response({
                'success': False,
                'message': 'pack_id et phone_number sont requis.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not new_pack.is_free and (not settings.GENIUSPAY_API_KEY or not settings.GENIUSPAY_API_SECRET):
            return Response({
                'success': False,
                'message': 'Service de paiement non configuré.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Récupérer l'abonnement actif
        current_sub = Subscription.objects.filter(user=user, is_active=True).first()

        # Bloquer uniquement si même pack ET non expiré
        if current_sub and current_sub.pack.id == new_pack.id and not current_sub.is_expired():
            return Response({
                'success': False,
                'message': 'Vous êtes déjà abonné à ce pack.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Déterminer le type de transaction
        previous_pack = None
        transaction_type = 'subscription'
        if current_sub:
            previous_pack = current_sub.pack
            transaction_type = 'renewal' if current_sub.is_expired() else 'upgrade'

        # ── PACK GRATUIT : activation directe sans paiement ──
        if new_pack.is_free:
            transaction = Transaction.objects.create(
                user=user,
                pack=new_pack,
                previous_pack=previous_pack,
                transaction_type=transaction_type,
                price_paid=0,
                payment_status='paid',
                phone_number=phone_number,
            )
            if current_sub:
                current_sub.is_active = False
                current_sub.save()
            Subscription.objects.create(user=user, pack=new_pack)
            return Response({
                'success': True,
                'is_free': True,
                'message': 'Abonnement gratuit activé avec succès.',
                'pack': new_pack.name,
                'amount': '0',
            }, status=status.HTTP_200_OK)

        # Créer la transaction en statut pending (sans token_pay pour l'instant)
        transaction = Transaction.objects.create(
            user=user,
            pack=new_pack,
            previous_pack=previous_pack,
            transaction_type=transaction_type,
            price_paid=new_pack.price,
            payment_status='pending',
            phone_number=phone_number,
        )

        # ── MODE MOCK (dev) : page de paiement locale ──
        if getattr(settings, 'PAYMENT_MOCK_MODE', False):
            mock_token = f"MOCK-{uuid.uuid4().hex[:10].upper()}"
            transaction.token_pay = mock_token
            transaction.save()
            payment_url = request.build_absolute_uri(
                f'/api/subscription/payment/mock/{mock_token}/'
            )
            return Response({
                'success': True,
                'message': '[MOCK] Page de paiement simulée.',
                'payment_url': payment_url,
                'token_pay': mock_token,
                'pack': new_pack.name,
                'amount': str(int(new_pack.price)),
            }, status=status.HTTP_200_OK)

        # ── MODE PRODUCTION : appel GeniusPay ──
        nom_client = f"{user.first_name or ''} {user.last_name or ''}".strip() or str(user.phone_number)

        payload = {
            "amount": int(new_pack.price),
            "currency": "XOF",
            "description": f"Abonnement {new_pack.name} - Corrige Moi",
            "customer": {"name": nom_client, "phone": phone_number},
            "metadata": {
                "userId": user.id,
                "transactionId": transaction.id,
                "packId": new_pack.id,
                "packName": new_pack.name,
            },
        }

        # Ajouter success_url/error_url uniquement si ce sont des URLs HTTP valides
        # (les deep links comme corrigemoi:// sont rejetés par GeniusPay)
        for field, key in [('success_url', 'return_url'), ('error_url', 'error_url')]:
            url = request.data.get(key, '')
            if url and url.startswith(('http://', 'https://')):
                payload[field] = url

        try:
            resp = requests.post(
                f"{settings.GENIUSPAY_BASE_URL}/payments",
                json=payload,
                headers=_geniuspay_headers(),
                timeout=15,
            )
            resp_data = resp.json()
        except Exception as e:
            print(f"[GeniusPay] EXCEPTION: {type(e).__name__}: {e}")
            transaction.payment_status = 'failed'
            transaction.save()
            return Response({
                'success': False,
                'message': 'Erreur de connexion au service de paiement.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not resp_data.get('success'):
            transaction.payment_status = 'failed'
            transaction.save()
            error = resp_data.get('error', {})
            return Response({
                'success': False,
                'message': error.get('message', 'Erreur lors de l\'initialisation du paiement.')
            }, status=status.HTTP_400_BAD_REQUEST)

        payment_data = resp_data['data']
        # checkout_url quand payment_method non spécifié, payment_url sinon (les deux sont présents)
        pay_url = payment_data.get('checkout_url') or payment_data.get('payment_url', '')
        transaction.token_pay = payment_data['reference']
        transaction.save()

        return Response({
            'success': True,
            'message': 'Paiement initié. Redirigez l\'utilisateur vers payment_url.',
            'payment_url': pay_url,
            'token_pay': payment_data['reference'],
            'pack': new_pack.name,
            'amount': str(int(new_pack.price)),
        }, status=status.HTTP_200_OK)


def _activate_subscription(transaction):
    """Active l'abonnement après confirmation du paiement (réutilisé par webhook et polling)."""
    user = transaction.user
    new_pack = transaction.pack

    remaining_images = 0
    remaining_questions = 0
    current_sub = Subscription.objects.filter(user=user, is_active=True).first()
    if current_sub:
        current_sub.is_active = False
        current_sub.save()
        remaining_images = current_sub.image_corrections_remaining
        remaining_questions = current_sub.chat_questions_remaining

    subscription = Subscription(
        user=user,
        pack=new_pack,
        image_corrections_remaining=new_pack.image_corrections_limit + remaining_images,
        chat_questions_remaining=new_pack.chat_questions_limit + remaining_questions,
    )
    if new_pack.duration > 0:
        subscription.expires_at = timezone.now() + timezone.timedelta(days=new_pack.duration)
    subscription.save()


def _verify_geniuspay_signature(timestamp: str, raw_body: bytes, signature: str) -> bool:
    """
    Vérifie la signature HMAC-SHA256 du webhook GeniusPay.
    Format GeniusPay : HMAC-SHA256(timestamp + "." + json_payload, webhook_secret)
    """
    secret = settings.GENIUSPAY_WEBHOOK_SECRET
    if not secret:
        return True  # Pas de secret configuré → skip en dev
    data_to_sign = timestamp.encode() + b'.' + raw_body
    expected = hmac.new(
        secret.encode(),
        data_to_sign,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@api_view(['POST'])
@permission_classes([AllowAny])
def geniuspay_webhook(request):
    """
    Webhook GeniusPay — reçoit les notifications de paiement en temps réel.
    Pas d'authentification JWT (appelé par les serveurs GeniusPay).
    Signature vérifiée via X-Webhook-Signature + X-Webhook-Timestamp.
    Retourne toujours HTTP 200.
    """
    signature = request.headers.get('X-Webhook-Signature', '')
    timestamp = request.headers.get('X-Webhook-Timestamp', '')
    event = request.headers.get('X-Webhook-Event') or request.data.get('event')

    if not _verify_geniuspay_signature(timestamp, request.body, signature):
        return Response({'status': 'invalid_signature'}, status=status.HTTP_200_OK)

    # Structure payload : { "event": "...", "data": { "reference": "...", "status": "...", ... } }
    tx_data = request.data.get('data', {})
    reference = tx_data.get('reference')

    if not reference:
        return Response({'status': 'ignored'}, status=status.HTTP_200_OK)

    transaction = Transaction.objects.filter(token_pay=reference).select_related(
        'user', 'pack'
    ).first()

    if not transaction:
        return Response({'status': 'not_found'}, status=status.HTTP_200_OK)

    if event == 'payment.success':
        if transaction.payment_status == 'paid':
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)
        transaction.payment_status = 'paid'
        transaction.payment_method = tx_data.get('provider') or tx_data.get('payment_method', '')
        transaction.save()
        _activate_subscription(transaction)

    elif event in ('payment.failed', 'payment.cancelled', 'payment.expired'):
        if transaction.payment_status not in ('paid', 'cancelled', 'failed'):
            transaction.payment_status = 'cancelled' if event in ('payment.cancelled', 'payment.expired') else 'failed'
            transaction.save()

    # payment.initiated, payment.refunded → rien à faire

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


GENIUSPAY_STATUS_MAP = {
    'completed': 'paid',
    'failed':    'failed',
    'cancelled': 'cancelled',
    'expired':   'cancelled',
}

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_status(request, token_pay):
    """
    GET : Vérifie le statut d'un paiement par token_pay.
    Interroge GeniusPay en temps réel si le paiement est encore pending.
    Le frontend peut poller cet endpoint toutes les 3-5 secondes.
    """
    transaction = Transaction.objects.filter(
        token_pay=token_pay,
        user=request.user
    ).select_related('pack').first()

    if not transaction:
        return Response({
            'success': False,
            'message': 'Transaction non trouvée.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Si déjà finalisé en base → retourner directement sans appel API
    if transaction.payment_status in ('paid', 'cancelled', 'failed'):
        return Response({
            'success': True,
            'payment_status': transaction.payment_status,
            'pack': transaction.pack.name,
            'amount': str(transaction.price_paid),
        })

    # Paiement encore pending → interroger GeniusPay en temps réel
    try:
        resp = requests.get(
            f"{settings.GENIUSPAY_BASE_URL}/payments/{token_pay}",
            headers=_geniuspay_headers(),
            timeout=10,
        )
        data = resp.json()
        geniuspay_status = data.get('data', {}).get('status', 'pending')
        our_status = GENIUSPAY_STATUS_MAP.get(geniuspay_status, 'pending')

        if our_status == 'paid' and transaction.payment_status != 'paid':
            transaction.payment_status = 'paid'
            transaction.payment_method = data['data'].get('payment_method', '')
            transaction.save()
            _activate_subscription(transaction)

        elif our_status in ('failed', 'cancelled') and transaction.payment_status == 'pending':
            transaction.payment_status = our_status
            transaction.save()

    except Exception:
        pass  # Erreur réseau temporaire → renvoyer le statut local

    return Response({
        'success': True,
        'payment_status': transaction.payment_status,
        'pack': transaction.pack.name,
        'amount': str(transaction.price_paid),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_payment(request, token_pay):
    """
    POST : Marque une transaction pending comme échouée (timeout côté app).
    """
    transaction = Transaction.objects.filter(
        token_pay=token_pay,
        user=request.user,
        payment_status='pending'
    ).first()

    if transaction:
        transaction.payment_status = 'failed'
        transaction.save()

    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_export_permission(request):
    """
    GET : Vérifie si l'utilisateur peut exporter ses corrections en PDF.
    Retourne 403 si la feature export_pdf n'est pas activée sur son pack.
    """
    subscription = (
        request.user.subscriptions
        .filter(is_active=True)
        .select_related('pack')
        .order_by('-created_at')
        .first()
    )
    if not subscription:
        return Response({'success': False, 'message': 'Aucun abonnement actif.'}, status=status.HTTP_403_FORBIDDEN)

    can_export = subscription.pack.get_feature('export_pdf', default=False)
    if not can_export:
        return Response({
            'success': False,
            'message': 'L\'export PDF n\'est pas inclus dans votre pack actuel.'
        }, status=status.HTTP_403_FORBIDDEN)

    return Response({'success': True, 'message': 'Export PDF autorisé.'})


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


@api_view(['GET'])
def subscription_history(request):
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

        # === QUOTAS ===
        pack = subscription.pack
        images_used = UsageLog.objects.filter(subscription=subscription, action='IMAGE_CORRECTION').count()
        questions_used = UsageLog.objects.filter(subscription=subscription, action='CHAT_QUESTION').count()
        images_total = subscription.image_corrections_remaining + images_used
        questions_total = subscription.chat_questions_remaining + questions_used
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

        # === USAGE TOTAL ===
        all_logs = UsageLog.objects.filter(subscription=subscription)
        total_images_used = all_logs.filter(action='IMAGE_CORRECTION').count()
        total_questions_used = all_logs.filter(action='CHAT_QUESTION').count()

        # === DERNIÈRE ACTIVITÉ ===
        last_log = all_logs.first()
        last_activity = last_log.timestamp if last_log else None

        # === USAGE PAR JOUR (7 derniers jours) ===
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
                'payment_status': last_transaction.payment_status,
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
