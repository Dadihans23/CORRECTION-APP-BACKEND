# =====================================================
# 🧩 STANDARD LIBRARY IMPORTS
# =====================================================
import csv
import io
import json
import uuid
import zipfile
import random
import secrets
import string
from decimal import Decimal
from datetime import datetime, timedelta
from io import BytesIO, StringIO

# =====================================================
# 📦 THIRD-PARTY LIBRARIES
# =====================================================
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from openpyxl import Workbook

# =====================================================
# 🧠 DJANGO CORE IMPORTS
# =====================================================
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.auth import (
    hashers,
    update_session_auth_hash,
    decorators as auth_decorators,
    authenticate,
    login as auth_login,
    logout as auth_logout,
)
from django.db.models import Max
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.contrib.auth.decorators import login_required
from functools import wraps


# =====================================================
# 🔒 DÉCORATEUR DE PROTECTION ADMIN
# =====================================================
def staff_required(view_func):
    """
    Protège une vue admin :
    - Non connecté       → redirige vers /admin/login/?next=<url>
    - Connecté non-staff → 403 Forbidden
    - Staff connecté     → accès autorisé
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect(f'/custom-admin/login/?next={request.path}')
        if not request.user.is_staff:
            from django.shortcuts import render as _render
            return _render(request, '403.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


# =====================================================
# 🧱 DJANGO APPS IMPORTS
# =====================================================
from authentification.models import CustomUser
from treatment.models import (
    ImageCorrection,
    CorrectionHistory,
    ChatSession,
    ChatMessage,
    SiteSettings,
    SupportTicket,
    SupportMessage,
)
from subscriptions.models import Pack, Subscription, UsageLog, Transaction, Feature, PackFeature

# =====================================================
# ⚙️ OTHER SETTINGS
# =====================================================
# Exemple : constante globale ou variable de config
# ITEMS_PER_PAGE = 20

# =====================================================
# 📊 ADMIN VIEWS
# =====================================================



def admin_home(request):
    """Vue d'accueil pour choisir entre dashboard utilisateur et admin"""
    return render(request, 'custom_admin/admin_home.html')


# ===============================================
# AUTHENTIFICATION CUSTOM ADMIN
# ===============================================

def admin_login(request):
    """Page de connexion du dashboard admin."""
    # Déjà connecté en tant que staff → dashboard directement
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/custom-admin/')

    next_url = request.GET.get('next', '/custom-admin/')
    error = None

    if request.method == 'POST':
        phone = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '/custom-admin/')

        user = authenticate(request, username=phone, password=password)
        if user is not None and user.is_staff:
            auth_login(request, user)
            return redirect(next_url)
        elif user is not None and not user.is_staff:
            error = "Ce compte n'a pas les droits d'administration."
        else:
            error = "Numéro de téléphone ou mot de passe incorrect."

    return render(request, 'custom_admin/login.html', {
        'error': error,
        'next': next_url,
        'year': datetime.now().year,
    })


def admin_logout(request):
    """Déconnexion du dashboard admin."""
    auth_logout(request)
    return redirect('/custom-admin/login/')


# ===============================================
# DASHBOARD PRINCIPAL
# ===============================================
# custom_admin/views.py



@staff_required
def admin_dashboard(request):

    # === FILTRE DATE ===
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timedelta(days=7)
    except:
        start_date = timezone.now().date() - timedelta(days=7)

    try:
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except:
        end_date = timezone.now().date()

    # Filtrer les données
    image_filter = Q(created_at__date__gte=start_date) & Q(created_at__date__lte=end_date)
    chat_filter = Q(created_at__date__gte=start_date) & Q(created_at__date__lte=end_date)
    transaction_filter = Q(created_at__date__gte=start_date) & Q(created_at__date__lte=end_date)

    # === STATS GÉNÉRALES (toujours total) ===
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    total_packs = Pack.objects.filter(is_active=True).count()
    active_subscriptions = Subscription.objects.filter(is_active=True).count()

    # === CORRECTIONS (période) ===
    total_image_corrections = ImageCorrection.objects.filter(image_filter).count()
    total_chat_questions = ChatMessage.objects.filter(role='user').filter(chat_filter).count()
    total_actions = total_image_corrections + total_chat_questions

    # === REVENUS (période) — uniquement les paiements confirmés ===
    revenue_period = Transaction.objects.filter(
        transaction_filter,
        transaction_type='subscription',
        payment_status='paid',
    ).aggregate(total=Sum('price_paid'))['total'] or 0

    total_revenue = Transaction.objects.filter(
        transaction_type='subscription',
        payment_status='paid',
    ).aggregate(total=Sum('price_paid'))['total'] or 0

    # === TOP PACKS (période) ===
    top_packs = Transaction.objects.filter(
        transaction_filter,
        transaction_type='subscription',
        payment_status='paid',
    ).values('pack__name').annotate(
        sales=Count('id'),
        revenue=Sum('price_paid')
    ).order_by('-revenue')[:5]

    # === GRAPH DATA (par jour) ===
    date_range = []
    current = start_date
    while current <= end_date:
        day_images = ImageCorrection.objects.filter(created_at__date=current).count()
        day_chat = ChatMessage.objects.filter(role='user', created_at__date=current).count()

        date_range.append({
            'date': current.strftime('%d/%m'),
            'images': day_images,
            'chat': day_chat,
            'total': day_images + day_chat
        })
        current += timedelta(days=1)

    # === CONTEXTE ===
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'total_packs': total_packs,
        'active_subscriptions': active_subscriptions,

        'total_image_corrections': total_image_corrections,
        'total_chat_questions': total_chat_questions,
        'total_actions': total_actions,

        'revenue_period': int(revenue_period),
        'total_revenue': int(total_revenue),

        'date_range': json.dumps(date_range),
        'top_packs': list(top_packs),

        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    }

    return render(request, 'custom_admin/admin/dashboard.html', context)
# ===============================================
# UTILISATEURS
# ===============================================# custom_admin/views.py



@staff_required
def admin_users(request):
    # RÉCUPÉRATION DES DONNÉES RÉELLES
    users = CustomUser.objects.all().order_by('-date_joined')
    
    # PAGINATION (comme le dashboard user)
    per_page = int(request.GET.get('per_page', 10))
    paginator = Paginator(users, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'custom_admin/admin/users.html', {
        'page_obj': page_obj,
    })



# custom_admin/views.py
@staff_required
def admin_user_create(request):

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip() or None
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        is_active = 'is_active' in request.POST
        is_staff = 'is_staff' in request.POST
        country = request.POST.get('country', '').strip() or None
        school_level = request.POST.get('school_level', '').strip() or None
        institution = request.POST.get('institution', '').strip() or None
        age = request.POST.get('age', '').strip()
        age = int(age) if age and age.isdigit() else None

        # === VALIDATION ===
        if not all([phone_number, first_name, last_name, password]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
            return render(request, 'custom_admin/admin/user_create.html')

        if len(password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return render(request, 'custom_admin/admin/user_create.html')

        if password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'custom_admin/admin/user_create.html')

        if CustomUser.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Ce numéro de téléphone existe déjà.")
            return render(request, 'custom_admin/admin/user_create.html')

        # === CRÉATION UTILISATEUR ===
        try:
            user = CustomUser.objects.create_user(
                phone_number=phone_number,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                is_active=is_active,
                is_staff=is_staff,
                country=country,
                school_level=school_level,
                institution=institution,
                age=age
            )
        except ValidationError as e:
            messages.error(request, f"Erreur : {e}")
            return render(request, 'custom_admin/admin/user_create.html')

        # # === PACK GRATUIT PAR DÉFAUT ===
        # free_pack = Pack.objects.filter(price=0, is_active=True).first()
        # if free_pack:
        #     Subscription.objects.create(
        #         user=user,
        #         pack=free_pack,
        #         image_corrections_remaining=free_pack.image_corrections_limit,
        #         chat_questions_remaining=free_pack.chat_questions_limit,
        #         is_active=True,
        #         expires_at=timezone.now() + timedelta(days=365) if free_pack.duration > 0 else None
        #     )

        messages.success(request, f"Utilisateur {phone_number} créé avec succès !")
        return redirect('custom_admin:user_detail', user_id=user.id)

    return render(request, 'custom_admin/admin/user_create.html')



@staff_required
def admin_user_detail(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    # === ABONNEMENTS ===
    subscriptions = Subscription.objects.filter(user=user).select_related('pack').order_by('-created_at')
    active_sub = subscriptions.filter(is_active=True, expires_at__gt=timezone.now()).first()

    # === QUOTAS RESTANTS ===
    if active_sub:
        images_remaining = active_sub.image_corrections_remaining
        chat_remaining = active_sub.chat_questions_remaining
    else:
        images_remaining = chat_remaining = 0

    # === STATS UTILISATEUR ===
    total_spent = Transaction.objects.filter(
        user=user, transaction_type='subscription', payment_status='paid'
    ).aggregate(total=Sum('price_paid'))['total'] or 0

    total_image_corrections = ImageCorrection.objects.filter(user=user).count()
    total_chat_questions = ChatMessage.objects.filter(session__user=user, role='user').count()
    total_actions = total_image_corrections + total_chat_questions

    # === DERNIÈRES ACTIONS (timeline) ===
    recent_actions = []

    # Transactions
    for trans in Transaction.objects.filter(user=user).order_by('-created_at')[:3]:
        recent_actions.append({
            'type': 'transaction',
            'icon': 'mdi-currency-usd',
            'color': 'success',
            'title': f'Achat {trans.pack.name}',
            'desc': f'{trans.price_paid} CFA',
            'date': trans.created_at,
        })

    # Corrections image
    for corr in ImageCorrection.objects.filter(user=user).order_by('-created_at')[:3]:
        recent_actions.append({
            'type': 'image',
            'icon': 'mdi-image-edit',
            'color': 'info',
            'title': 'Correction photo',
            'desc': f'{corr.domaine} - {corr.niveau}',
            'date': corr.created_at,
        })

    # Chat
    for msg in ChatMessage.objects.filter(session__user=user, role='user').order_by('-created_at')[:3]:
        recent_actions.append({
            'type': 'chat',
            'icon': 'mdi-chat',
            'color': 'primary',
            'title': 'Question chat',
            'desc': msg.content[:50] + ('...' if len(msg.content) > 50 else ''),
            'date': msg.created_at,
        })

    # Trier par date
    recent_actions = sorted(recent_actions, key=lambda x: x['date'], reverse=True)[:10]

    context = {
        'user': user,
        'active_sub': active_sub,
        'subscriptions': subscriptions,
        'images_remaining': images_remaining,
        'chat_remaining': chat_remaining,
        'total_spent': total_spent,
        'total_image_corrections': total_image_corrections,
        'total_chat_questions': total_chat_questions,
        'total_actions': total_actions,
        'recent_actions': recent_actions,
    }

    return render(request, 'custom_admin/admin/user_detail.html', context)




@staff_required
def admin_user_edit(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        # Champs obligatoires
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email') or None
        user.country = request.POST.get('country') or None
        user.school_level = request.POST.get('school_level') or None
        user.institution = request.POST.get('institution') or None

        # Champs optionnels
        age = request.POST.get('age')
        user.age = int(age) if age and age.isdigit() else None

        # Permissions
        user.is_active = 'is_active' in request.POST
        user.is_staff = 'is_staff' in request.POST

        # Validation basique
        if not user.first_name or not user.last_name:
            messages.error(request, "Le prénom et le nom sont obligatoires.")
        else:
            user.save()
            messages.success(request, "Modifications sauvegardées avec succès.")
            return redirect('custom_admin:user_detail', user_id=user.id)

    return render(request, 'custom_admin/admin/user_edit.html', {'user': user})



@staff_required
def admin_user_delete(request, user_id):

    user = get_object_or_404(CustomUser, id=user_id)

    # Empêche la suppression de soi-même
    if user == request.user:
        return JsonResponse({'status': 'error', 'message': 'Vous ne pouvez pas vous supprimer vous-même.'})

    user_phone = user.phone_number
    user.delete()

    return JsonResponse({
        'status': 'success',
        'message': f'Utilisateur {user_phone} supprimé avec succès !'
    })
    
    
    
    
    
    
# ===============================================
# PACKS
# ===============================================







# custom_admin/views.py
from django.db.models import Sum

@staff_required
def admin_packs(request):

    packs = Pack.objects.all().order_by('-is_best_plan', 'price')

    # ON PRÉCALCULE LES REVENUS ICI
    for pack in packs:
        revenue = Transaction.objects.filter(
            pack=pack,
            transaction_type='subscription',
            payment_status='paid',
        ).aggregate(total=Sum('price_paid'))['total'] or 0
        pack.revenue = int(revenue)  # On ajoute un attribut temporaire

    per_page = int(request.GET.get('per_page', 10))
    paginator = Paginator(packs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'custom_admin/admin/packs.html', {
        'page_obj': page_obj,
        'per_page': per_page,
    })



@staff_required
def admin_pack_create(request):

    if request.method == 'POST':
        try:
            # Récupération sécurisée des features d'affichage (texte libre)
            features_raw = request.POST.get('features', '[]')
            try:
                features = json.loads(features_raw) if features_raw else []
            except json.JSONDecodeError:
                features = features_raw.splitlines()
                features = [f.strip() for f in features if f.strip()]

            # Création du pack
            pack = Pack.objects.create(
                name=request.POST['name'].strip(),
                price=request.POST['price'],
                description=request.POST['description'].strip(),
                image_corrections_limit=int(request.POST.get('image_corrections_limit', 0)),
                chat_questions_limit=int(request.POST.get('chat_questions_limit', 0)),
                duration=int(request.POST['duration']),
                is_best_plan='is_best_plan' in request.POST,
                is_active='is_active' in request.POST,
                features=features
            )

            # Restrictions fonctionnelles (PackFeature)
            _save_pack_features(pack, request.POST)

            messages.success(request, f'Pack "{pack.name}" créé avec succès !')
            return redirect('custom_admin:pack_detail', pack_id=pack.id)

        except Exception as e:
            messages.error(request, f'Erreur : {str(e)}')

    all_features = Feature.objects.all()
    return render(request, 'custom_admin/admin/pack_create.html', {'all_features': all_features})


@staff_required
def admin_pack_detail(request, pack_id):
    pack = get_object_or_404(Pack, id=pack_id)
    
    # Stats réelles
    subscribers = pack.subscriptions.filter(is_active=True).count()
    total_revenue = Transaction.objects.filter(
        pack=pack, transaction_type='subscription', payment_status='paid'
    ).aggregate(total=Sum('price_paid'))['total'] or 0

    # Dernières souscriptions
    recent_subs = pack.subscriptions.select_related('user').order_by('-created_at')[:10]

    context = {
        'pack': pack,
        'subscribers': subscribers,
        'total_revenue': int(total_revenue),
        'recent_subs': recent_subs,
    }
    return render(request, 'custom_admin/admin/pack_detail.html', context)


@staff_required
def admin_pack_edit(request, pack_id):
    pack = get_object_or_404(Pack, id=pack_id)

    if request.method == 'POST':
        features = request.POST.get('features', '[]')
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except json.JSONDecodeError:
                features = []

        pack.name = request.POST['name']
        pack.price = request.POST['price']
        pack.description = request.POST['description']
        pack.image_corrections_limit = request.POST.get('image_corrections_limit', 0)
        pack.chat_questions_limit = request.POST.get('chat_questions_limit', 0)
        pack.duration = int(request.POST['duration'])
        pack.is_best_plan = 'is_best_plan' in request.POST
        pack.is_active = 'is_active' in request.POST
        pack.features = features
        pack.save()

        # Restrictions fonctionnelles (PackFeature)
        _save_pack_features(pack, request.POST)

        messages.success(request, f'Pack mis à jour !')
        return redirect('custom_admin:pack_detail', pack_id=pack.id)

    all_features = Feature.objects.all()
    current_pack_features = {pf.feature.key: pf.value for pf in pack.pack_features.select_related('feature')}
    return render(request, 'custom_admin/admin/pack_edit.html', {
        'pack': pack,
        'all_features': all_features,
        'current_pack_features_json': json.dumps(current_pack_features),
    })



@staff_required
def admin_pack_delete(request, pack_id):

    if request.method == 'POST':
        pack = get_object_or_404(Pack, id=pack_id)
        name = pack.name
        pack.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Pack "{name}" supprimé avec succès !'
        })

    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


# -----------------------------------------------
# Helper : sauvegarde des PackFeature depuis POST
# -----------------------------------------------
def _save_pack_features(pack, post_data):
    """
    Lit les champs de la forme `feat_<key>` dans POST et
    crée/met à jour les PackFeature correspondants.
    Pour les booléens : présence du champ = true, absence = false.
    Pour les entiers : valeur directe.
    """
    all_features = Feature.objects.all()
    for feature in all_features:
        field_name = f'feat_{feature.key}'
        if feature.feature_type == 'boolean':
            value = 'true' if field_name in post_data else 'false'
        else:
            raw = post_data.get(field_name, '').strip()
            value = raw if raw else feature.default_value
        PackFeature.objects.update_or_create(
            pack=pack, feature=feature,
            defaults={'value': value},
        )


# ===============================================
# FONCTIONNALITÉS (catalogue)
# ===============================================

@staff_required
def admin_features(request):
    features = Feature.objects.all()
    return render(request, 'custom_admin/admin/features.html', {'features': features})


@staff_required
def admin_feature_create(request):
    if request.method == 'POST':
        try:
            Feature.objects.create(
                key=request.POST['key'].strip().lower().replace(' ', '_'),
                label=request.POST['label'].strip(),
                description=request.POST.get('description', '').strip(),
                feature_type=request.POST.get('feature_type', 'boolean'),
                default_value=request.POST.get('default_value', 'false').strip(),
            )
            messages.success(request, 'Fonctionnalité créée !')
        except Exception as e:
            messages.error(request, f'Erreur : {str(e)}')
        return redirect('custom_admin:features')
    return render(request, 'custom_admin/admin/feature_form.html', {'action': 'create'})


@staff_required
def admin_feature_edit(request, feature_id):
    feature = get_object_or_404(Feature, id=feature_id)
    if request.method == 'POST':
        try:
            feature.label = request.POST['label'].strip()
            feature.description = request.POST.get('description', '').strip()
            feature.feature_type = request.POST.get('feature_type', 'boolean')
            feature.default_value = request.POST.get('default_value', 'false').strip()
            feature.save()
            messages.success(request, 'Fonctionnalité mise à jour !')
        except Exception as e:
            messages.error(request, f'Erreur : {str(e)}')
        return redirect('custom_admin:features')
    return render(request, 'custom_admin/admin/feature_form.html', {
        'feature': feature, 'action': 'edit',
    })


@staff_required
def admin_feature_delete(request, feature_id):
    if request.method == 'POST':
        feature = get_object_or_404(Feature, id=feature_id)
        feature.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)


# ===============================================
# ABONNEMENTS
# ===============================================


# custom_admin/views.py
@staff_required
def admin_subscriptions(request):

    # === FILTRES ===
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', 'all')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    per_page = int(request.GET.get('per_page', 10))

    subs = Subscription.objects.select_related('user', 'pack').order_by('-created_at')

    # Recherche par téléphone ou nom
    if search:
        subs = subs.filter(
            Q(user__phone_number__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    # Filtre statut
    if status == 'active':
        subs = subs.filter(is_active=True).exclude(expires_at__lt=timezone.now())
    elif status == 'inactive':
        subs = subs.filter(Q(is_active=False) | Q(expires_at__lt=timezone.now()))

    # Filtre date
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            subs = subs.filter(created_at__gte=start)
        except:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            subs = subs.filter(created_at__lt=end + timedelta(days=1))
        except:
            pass

    # === STATS ===
    total_subs = Subscription.objects.count()
    today_subs = Subscription.objects.filter(created_at__date=timezone.now().date()).count()
    period_subs = subs.count()

    # Pagination
    paginator = Paginator(subs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'per_page': per_page,
        'total_subs': total_subs,
        'today_subs': today_subs,
        'period_subs': period_subs,
    }
    return render(request, 'custom_admin/admin/subscriptions.html', context)


@staff_required
def admin_subscription_detail(request, subscription_id):
    sub = get_object_or_404(
        Subscription.objects.select_related('user', 'pack'),
        id=subscription_id
    )

    # Calculs quotas
    images_limit = sub.pack.image_corrections_limit or 999999
    chat_limit = sub.pack.chat_questions_limit or 999999

    images_used = images_limit - sub.image_corrections_remaining
    chat_used = chat_limit - sub.chat_questions_remaining

    # Usage récent
    recent_logs = UsageLog.objects.filter(subscription=sub).order_by('-timestamp')[:10]

    context = {
        'subscription': sub,
        'images_used': images_used,
        'chat_used': chat_used,
        'images_limit': images_limit,
        'chat_limit': chat_limit,
        'recent_logs': recent_logs,
    }
    return render(request, 'custom_admin/admin/subscription_detail.html', context)


@staff_required
def admin_subscription_edit(request, subscription_id):
    sub = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        try:
            sub.image_corrections_remaining = int(request.POST.get('images', sub.image_corrections_remaining))
            sub.chat_questions_remaining = int(request.POST.get('chat', sub.chat_questions_remaining))
            sub.is_active = 'is_active' in request.POST
            sub.save()
            messages.success(request, 'Abonnement mis à jour avec succès !')
        except ValueError:
            messages.error(request, 'Veuillez entrer des nombres valides.')
        
        return redirect('custom_admin:subscription_detail', subscription_id=sub.id)

    return render(request, 'custom_admin/admin/subscription_edit.html', {
        'subscription': sub,
    })


@staff_required
def admin_subscription_create(request):
    if request.method == 'POST':
        try:
            phone = request.POST.get('phone_number')
            user = CustomUser.objects.get(phone_number=phone)
            pack = Pack.objects.get(id=request.POST.get('pack'))
            is_active = 'is_active' in request.POST

            # Désactiver ancien abonnement actif
            Subscription.objects.filter(user=user, is_active=True).update(is_active=False)

            # Créer nouveau
            sub = Subscription.objects.create(
                user=user,
                pack=pack,
                image_corrections_remaining=pack.image_corrections_limit,
                chat_questions_remaining=pack.chat_questions_limit,
                is_active=is_active
            )
            messages.success(request, f'Abonnement {pack.name} créé pour {user.phone_number}')
            return redirect('custom_admin:subscriptions')
        except Exception as e:
            messages.error(request, f'Erreur: {e}')

    users = CustomUser.objects.all()
    packs = Pack.objects.filter(is_active=True)
    return render(request, 'custom_admin/admin/subscription_create.html', {
        'users': users,
        'packs': packs,
    })
    
    
    

from django.db.models import Sum, Count, Q, DecimalField
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal


# ===============================================
# STATS FACTURATION
# ===============================================
@staff_required
def admin_billing_stats(request):

    today = timezone.now()
    monthly_revenue = []
    monthly_labels = []

    # === REVENUS MENSUELS (7 derniers mois) ===
    for i in range(6, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        next_month = month_date.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)

        revenue = Transaction.objects.filter(
            transaction_type='subscription',
            payment_status='paid',
            created_at__gte=month_start,
            created_at__lte=month_end
        ).aggregate(total=Sum('price_paid'))['total'] or Decimal('0.00')

        monthly_revenue.append(float(revenue))
        monthly_labels.append(month_date.strftime('%b %Y'))

    # === TOP 5 UTILISATEURS PAR REVENUS ===
    top_revenue_users = Transaction.objects.filter(
        transaction_type='subscription', payment_status='paid'
    ).values('user__phone_number', 'pack__name').annotate(
        total_revenue=Sum('price_paid')
    ).order_by('-total_revenue')[:5]

    top_users_formatted = [
        {
            'user': f"{u['user__phone_number']} ({u['pack__name']})",
            'revenue': float(u['total_revenue'])
        }
        for u in top_revenue_users
    ]

    # === MÉTHODES DE PAIEMENT (simulé car pas de champ) ===
    # Tu peux ajouter un champ `payment_method` dans Transaction plus tard
    payment_methods = {
        'mobile_money': Transaction.objects.filter(transaction_type='subscription', payment_status='paid').count(),
        'card': 0,
        'bank': 0,
        'admin': 0
    }

    # === STATUTS ABONNEMENTS ===
    now = timezone.now()
    subscription_stats = {
        'active': Subscription.objects.filter(is_active=True).count(),
        'expired': Subscription.objects.filter(is_active=False, expires_at__lt=now).count(),
        'pending': Subscription.objects.filter(is_active=True, expires_at__gt=now).count(),
        'free_trial': Subscription.objects.filter(pack__price=0, is_active=True).count()
    }

    # === STATS GLOBAUX ===
    total_revenue = float(Transaction.objects.filter(transaction_type='subscription', payment_status='paid').aggregate(total=Sum('price_paid'))['total'] or 0)
    this_month_revenue = float(Transaction.objects.filter(
        transaction_type='subscription',
        payment_status='paid',
        created_at__month=today.month,
        created_at__year=today.year
    ).aggregate(total=Sum('price_paid'))['total'] or 0)

    last_month = today.replace(day=1) - timedelta(days=1)
    last_month_revenue = float(Transaction.objects.filter(
        transaction_type='subscription',
        payment_status='paid',
        created_at__month=last_month.month,
        created_at__year=last_month.year
    ).aggregate(total=Sum('price_paid'))['total'] or 0)

    growth_rate = round(((this_month_revenue - last_month_revenue) / last_month_revenue * 100), 1) if last_month_revenue > 0 else 0

    billing_data = {
        'monthly_revenue': json.dumps(monthly_revenue),
        'monthly_labels': json.dumps(monthly_labels),
        'top_revenue_users': top_users_formatted,
        'payment_methods': payment_methods,
        'subscription_stats': subscription_stats,
        'total_revenue': total_revenue,
        'this_month': this_month_revenue,
        'last_month': last_month_revenue,
        'growth_rate': growth_rate
    }

    return render(request, 'custom_admin/admin/billing_stats.html', {'billing': billing_data})


# ===============================================
# STATS UTILISATEURS
# ===============================================

@staff_required
def admin_user_stats(request):

    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # === TOTAL UTILISATEURS ===
    total_users = CustomUser.objects.count()

    # === UTILISATEURS ACTIFS (abonnés + activité récente) ===
    active_subscriptions = Subscription.objects.filter(is_active=True).count()
    recent_activity_users = UsageLog.objects.filter(
        timestamp__gte=now - timedelta(days=30)
    ).values('subscription__user').distinct().count()
    active_users = active_subscriptions + recent_activity_users

    # === NOUVEAUX CE MOIS ===
    new_this_month = CustomUser.objects.filter(
        date_joined__gte=this_month_start
    ).count()

    # === RÉPARTITION PAR PACK ===
    all_packs = Pack.objects.filter(is_active=True)
    user_distribution = {}
    for pack in all_packs:
        count = Subscription.objects.filter(pack=pack, is_active=True).count()
        user_distribution[pack.name] = count

    # Utilisateurs sans abonnement actif
    users_with_sub = Subscription.objects.filter(is_active=True).values_list('user', flat=True).distinct()
    free_users = CustomUser.objects.exclude(id__in=users_with_sub).count()
    user_distribution['Gratuit'] = free_users

    # Pourcentages
    user_distribution_with_percentage = {}
    for pack_name, count in user_distribution.items():
        percentage = (count * 100 / total_users) if total_users > 0 else 0
        user_distribution_with_percentage[pack_name] = {
            'count': count,
            'percentage': round(percentage, 1)
        }

    # === CROISSANCE MENSUELLE (4 derniers mois) ===
    user_growth_data = []
    for i in range(3, -1, -1):
        month_date = (now - timedelta(days=30 * i)).replace(day=1)
        month_start = month_date
        month_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        new_users = CustomUser.objects.filter(
            date_joined__range=[month_start, month_end]
        ).count()

        active_in_month = UsageLog.objects.filter(
            timestamp__range=[month_start, month_end]
        ).values('subscription__user').distinct().count()

        user_growth_data.append({
            'month': month_date.strftime('%b'),
            'new_users': new_users,
            'active_users': active_in_month
        })

    # === RÉTENTION ===
    total_new_7d = CustomUser.objects.filter(date_joined__gte=now - timedelta(days=7)).count()
    active_7d = UsageLog.objects.filter(timestamp__gte=now - timedelta(days=7)).values('subscription__user').distinct().count()
    retention_7d = (active_7d / total_new_7d * 100) if total_new_7d > 0 else 0

    total_new_30d = CustomUser.objects.filter(date_joined__gte=now - timedelta(days=30)).count()
    active_30d = UsageLog.objects.filter(timestamp__gte=now - timedelta(days=30)).values('subscription__user').distinct().count()
    retention_30d = (active_30d / total_new_30d * 100) if total_new_30d > 0 else 0

    user_retention = {
        'day_1': 95,  # estimé
        'day_7': round(retention_7d, 1),
        'day_30': round(retention_30d, 1),
        'day_90': round(retention_30d * 0.7, 1),
    }

    # === TOP 5 UTILISATEURS PAR USAGE (Image + Chat) ===
    top_users = UsageLog.objects.values('subscription__user__phone_number').annotate(
        total_actions=Count('id')
    ).order_by('-total_actions')[:5]

    top_users_formatted = []
    for u in top_users:
        user = CustomUser.objects.filter(phone_number=u['subscription__user__phone_number']).first()
        if user:
            image_count = ImageCorrection.objects.filter(user=user).count()
            chat_count = ChatMessage.objects.filter(session__user=user, role='user').count()
            top_users_formatted.append({
                'user': user.phone_number,
                'email': user.email or "—",
                'actions': u['total_actions'],
                'images': image_count,
                'chat': chat_count,
            })

    # === CONTEXTE FINAL ===
    context = {
        'user_stats': {
            'total_users': total_users,
            'active_users': active_users,
            'new_this_month': new_this_month,
            'user_growth_data': user_growth_data,
            'user_growth_data_json': json.dumps(user_growth_data),
            'user_retention': user_retention,
            'top_users_by_usage': top_users_formatted,
            'user_distribution': user_distribution,
            'user_distribution_with_percentage': user_distribution_with_percentage,
            'pack_names': json.dumps(list(user_distribution.keys())),
            'pack_counts': json.dumps(list(user_distribution.values())),
        }
    }

    return render(request, 'custom_admin/admin/user_stats.html', context)



# ===============================================
# ANALYTICS GÉNÉRAL
# ===============================================# custom_admin/views.py



@staff_required
def admin_analytics(request):

    now = timezone.now()
    period = int(request.GET.get('period', 7))  # 7, 30 ou 90
    days_ago = now - timedelta(days=period)

    # === KPI ===
    this_month = now.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    new_users_this_month = CustomUser.objects.filter(date_joined__gte=this_month).count()
    new_users_last_month = CustomUser.objects.filter(date_joined__gte=last_month, date_joined__lt=this_month).count()
    user_growth = round(((new_users_this_month - new_users_last_month) / new_users_last_month * 100), 1) if new_users_last_month else 100

    total_revenue = float(Transaction.objects.filter(transaction_type='subscription', payment_status='paid').aggregate(t=Sum('price_paid'))['t'] or 0)

    # Rétention 30j
    users_30d_ago = CustomUser.objects.filter(date_joined__gte=now - timedelta(days=30))
    active_30d = set(ImageCorrection.objects.filter(created_at__gte=now - timedelta(days=30)).values_list('user_id', flat=True))
    active_30d |= set(ChatMessage.objects.filter(created_at__gte=now - timedelta(days=30), role='user').values_list('session__user_id', flat=True))
    retention = round(len(active_30d) / users_30d_ago.count() * 100, 1) if users_30d_ago.exists() else 0

    total_actions = ImageCorrection.objects.count() + ChatMessage.objects.filter(role='user').count()

    # === DONNÉES PAR JOUR ===
    dates = []
    daily_images = []
    daily_chat = []
    daily_revenue = []
    day_labels = []

    for i in range(period - 1, -1, -1):
        date = (now - timedelta(days=i)).date()
        dates.append(date)
        day_labels.append(date.strftime('%a %d'))

        img_count = ImageCorrection.objects.filter(created_at__date=date).count()
        chat_count = ChatMessage.objects.filter(role='user', created_at__date=date).count()
        rev = Transaction.objects.filter(created_at__date=date, transaction_type='subscription', payment_status='paid').aggregate(r=Sum('price_paid'))['r'] or 0

        daily_images.append(img_count)
        daily_chat.append(chat_count)
        daily_revenue.append(float(rev))

    # === TOP PACKS ===
    top_packs = Transaction.objects.filter(
        created_at__gte=days_ago,
        transaction_type='subscription',
        payment_status='paid',
    ).values('pack__name').annotate(
        sales=Count('id'),
        revenue=Sum('price_paid')
    ).order_by('-revenue')[:5]

    top_packs_list = [
        {'name': p['pack__name'], 'sales': p['sales'], 'revenue': float(p['revenue'] or 0)}
        for p in top_packs
    ]

    # === UTILISATION PAR TYPE ===
    images_total = ImageCorrection.objects.filter(created_at__gte=days_ago).count()
    chat_total = ChatMessage.objects.filter(role='user', created_at__gte=days_ago).count()

    # === NIVEAU SCOLAIRE ===
    level_data = ImageCorrection.objects.filter(created_at__gte=days_ago).values('niveau').annotate(c=Count('id')).order_by('-c')[:6]
    level_labels = [x['niveau'] or 'Non spécifié' for x in level_data]
    level_values = [x['c'] for x in level_data]

    # === LIVE ===
    live_users = len(set(
        ImageCorrection.objects.filter(created_at__gte=now - timedelta(minutes=5)).values_list('user_id', flat=True)
    ))
    live_actions = ImageCorrection.objects.filter(created_at__gte=now - timedelta(minutes=10)).count() + \
                   ChatMessage.objects.filter(created_at__gte=now - timedelta(minutes=10), role='user').count()

    context = {
        'analytics': {
            'period': period,
            'day_labels': json.dumps(day_labels),
            'daily_images': json.dumps(daily_images),
            'daily_chat': json.dumps(daily_chat),
            'daily_revenue': json.dumps(daily_revenue),
            'top_packs': top_packs_list,
            'user_growth': {
                'this_month': new_users_this_month,
                'growth_rate': user_growth
            },
            'kpi': {
                'total_revenue': total_revenue,
                'retention_rate': retention,
                'total_actions': total_actions,
            },
            'usage': {
                'labels': json.dumps(['Corrections photo', 'Questions chat']),
                'series': json.dumps([images_total, chat_total])
            },
            'levels': {
                'labels': json.dumps(level_labels),
                'series': json.dumps(level_values)
            },
            'live': {
                'active_users': live_users,
                'actions_last_10min': live_actions
            }
        }
    }

    return render(request, 'custom_admin/admin/analytics.html', context)


# ===============================================
# RAPPORTS
# ===============================================
@staff_required
def admin_reports(request):

    now = timezone.now()

    # === RAPPORTS DISPONIBLES ===
    available_reports = [
        {
            'name': 'Rapport mensuel des ventes',
            'type': 'sales',
            'last_generated': Transaction.objects.filter(transaction_type='subscription', payment_status='paid').aggregate(m=Max('created_at'))['m'] or now - timedelta(days=1),
            'total_sales': Transaction.objects.filter(transaction_type='subscription', payment_status='paid').count(),
            'total_revenue': float(Transaction.objects.filter(transaction_type='subscription', payment_status='paid').aggregate(t=Sum('price_paid'))['t'] or 0)
        },
        {
            'name': 'Analyse corrections photo',
            'type': 'images',
            'last_generated': ImageCorrection.objects.aggregate(m=Max('created_at'))['m'] or now - timedelta(hours=6),
            'total_corrections': ImageCorrection.objects.count(),
            'top_domain': ImageCorrection.objects.values('domaine').annotate(c=Count('id')).order_by('-c').first()
        },
        {
            'name': 'Rapport utilisateurs actifs',
            'type': 'users',
            'last_generated': CustomUser.objects.filter(date_joined__gte=now - timedelta(days=30)).aggregate(m=Max('date_joined'))['m'] or now - timedelta(hours=2),
            'active_users': ImageCorrection.objects.filter(created_at__gte=now - timedelta(days=30)).values('user').distinct().count(),
            'new_users': CustomUser.objects.filter(date_joined__gte=now - timedelta(days=30)).count()
        }
    ]

    # === HISTORIQUE ===
    report_history = []
    recent_transactions = Transaction.objects.filter(transaction_type='subscription', payment_status='paid').order_by('-created_at')[:5]
    for i, t in enumerate(recent_transactions, 1):
        report_history.append({
            'id': i,
            'name': f'Vente - {t.created_at.strftime("%d/%m")}',
            'type': 'sales',
            'period': t.created_at.strftime("%d/%m/%Y"),
            'generated_at': t.created_at,
            'status': 'completed',
            'amount': float(t.price_paid)
        })

    # === PROGRAMMÉS ===
    next_monday = now + timedelta(days=(7 - now.weekday()))
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)

    scheduled_reports = [
        {'name': 'Rapport hebdo', 'frequency': 'lundis', 'next_run': next_monday, 'type': 'sales'},
        {'name': 'Rapport mensuel', 'frequency': '1er du mois', 'next_run': next_month, 'type': 'financial'}
    ]

    reports_data = {
        'available_reports': available_reports,
        'report_history': report_history,
        'scheduled_reports': scheduled_reports,
        'total_reports': len(report_history)
    }

    return render(request, 'custom_admin/admin/reports.html', {'reports': reports_data})


# ===============================================
# GÉNÉRATION PDF / EXCEL / CSV
# ===============================================
def generate_sales_report(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, spaceAfter=30)

    transactions = Transaction.objects.filter(transaction_type='subscription', payment_status='paid').order_by('-created_at')
    total = float(transactions.aggregate(t=Sum('price_paid'))['t'] or 0)

    story.append(Paragraph("RAPPORT VENTES - CORRIGE MOI", title_style))
    story.append(Spacer(1, 20))

    data = [['#', 'Pack', 'Utilisateur', 'Montant (CFA)', 'Date']]
    for i, t in enumerate(transactions[:20], 1):
        data.append([i, t.pack.name, t.user.phone_number, f"{t.price_paid}", t.created_at.strftime("%d/%m/%Y")])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>TOTAL: {total:,.0f} CFA</b>", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_ventes_corrige_moi.pdf"'
    return response


def generate_images_report(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Corrections Photo"
    ws.append(['Date', 'Utilisateur', 'Domaine', 'Niveau', 'Heure'])

    corrections = ImageCorrection.objects.order_by('-created_at')[:1000]
    for c in corrections:
        ws.append([
            c.created_at.strftime("%d/%m/%Y"),
            c.user.phone_number,
            c.domaine,
            c.niveau,
            c.created_at.strftime("%H:%M")
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="corrections_photo.xlsx"'
    return response


def generate_users_report(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs_actifs.csv"'
    writer = csv.writer(response)
    writer.writerow(['Téléphone', 'Inscrit le', 'Dernière correction', 'Pack', 'Images restantes'])

    active_users = ImageCorrection.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).values('user__phone_number', 'user__date_joined', 'user__subscriptions__pack__name', 'user__subscriptions__image_corrections_remaining').distinct()

    for u in active_users:
        writer.writerow([
            u['user__phone_number'],
            u['user__date_joined'],
            'Actif',
            u['user__subscriptions__pack__name'] or 'Gratuit',
            u['user__subscriptions__image_corrections_remaining'] or 0
        ])

    return response

# ===========================================
# **DOWNLOAD RAPPORT SPÉCIFIQUE**
# ===========================================# custom_admin/views.py (ajoute à la suite)



# ===============================================
# TÉLÉCHARGEMENT PAR TYPE
# ===============================================
@staff_required
def download_report(request, report_type):
    """Télécharge un rapport selon le type"""

    if report_type == 'sales':
        return generate_sales_report(request)
    elif report_type == 'images':
        return generate_images_report(request)
    elif report_type == 'users':
        return generate_users_report(request)
    else:
        return HttpResponse("Rapport non trouvé", status=404)


# ===============================================
# ZIP TOUS LES RAPPORTS
# ===============================================
@staff_required
def export_all_reports(request):
    """Génère un ZIP avec les 3 rapports"""

    buffer = io.BytesIO()
    zip_file = zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED)

    # === 1. PDF VENTES ===
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, spaceAfter=30)

    transactions = Transaction.objects.filter(transaction_type='subscription', payment_status='paid').order_by('-created_at')
    total = float(transactions.aggregate(t=Sum('price_paid'))['t'] or 0)

    story.append(Paragraph("RAPPORT VENTES - CORRIGE MOI", title_style))
    story.append(Spacer(1, 20))

    data = [['#', 'Pack', 'Téléphone', 'Montant (CFA)', 'Date']]
    for i, t in enumerate(transactions[:50], 1):
        data.append([i, t.pack.name, t.user.phone_number, f"{t.price_paid:,}", t.created_at.strftime("%d/%m/%Y")])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>TOTAL: {total:,.0f} CFA</b>", styles['Normal']))

    doc.build(story)
    pdf_buffer.seek(0)
    zip_file.writestr('rapport_ventes_corrige_moi.pdf', pdf_buffer.getvalue())

    # === 2. EXCEL CORRECTIONS PHOTO ===
    excel_buffer = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Corrections Photo"
    ws.append(['Date', 'Téléphone', 'Domaine', 'Niveau', 'Heure'])

    corrections = ImageCorrection.objects.select_related('user').order_by('-created_at')[:1000]
    for c in corrections:
        ws.append([
            c.created_at.strftime("%d/%m/%Y"),
            c.user.phone_number,
            c.domaine,
            c.niveau,
            c.created_at.strftime("%H:%M")
        ])

    wb.save(excel_buffer)
    excel_buffer.seek(0)
    zip_file.writestr('corrections_photo.xlsx', excel_buffer.getvalue())

    # === 3. CSV UTILISATEURS ACTIFS ===
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['Téléphone', 'Inscrit le', 'Dernière correction', 'Pack', 'Images restantes'])

    active_users = ImageCorrection.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).values(
        'user__phone_number', 'user__date_joined',
        'user__subscriptions__pack__name', 'user__subscriptions__image_corrections_remaining'
    ).distinct()

    for u in active_users:
        writer.writerow([
            u['user__phone_number'],
            u['user__date_joined'].strftime("%d/%m/%Y"),
            'Actif (30j)',
            u['user__subscriptions__pack__name'] or 'Gratuit',
            u['user__subscriptions__image_corrections_remaining'] or 0
        ])

    csv_content = csv_buffer.getvalue()
    zip_file.writestr('utilisateurs_actifs.csv', csv_content)

    # === FINALISE ZIP ===
    zip_file.close()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="rapports_corrige_moi_complet.zip"'
    return response








@staff_required
def admin_settings(request):

    settings = SiteSettings.get_instance()

    if request.method == 'POST':
        settings.support_email = request.POST.get('support_email', settings.support_email)
        settings.support_whatsapp = request.POST.get('support_whatsapp', settings.support_whatsapp)
        settings.support_phone = request.POST.get('support_phone', settings.support_phone)
        settings.support_facebook = request.POST.get('support_facebook', settings.support_facebook)
        settings.support_instagram = request.POST.get('support_instagram', settings.support_instagram)

        settings.site_name = request.POST.get('site_name', settings.site_name)
        settings.maintenance_mode = request.POST.get('maintenance_mode') == 'on'
        settings.allow_registrations = request.POST.get('allow_registrations') == 'on'

        # Reconstruire WhatsApp avec +225
        whatsapp = request.POST.get('support_whatsapp', '')
        if whatsapp and not whatsapp.startswith('+'):
            settings.support_whatsapp = '+225' + whatsapp

        settings.save()
        messages.success(request, 'Paramètres sauvegardés avec succès !')
        return redirect('custom_admin:settings')

    context = {'settings': settings}
    return render(request, 'custom_admin/admin/settings.html', context)










# =====================================================
# 📸 HISTORIQUE DES CORRECTIONS
# =====================================================

@staff_required
def admin_corrections_history(request):

    corrections = CorrectionHistory.objects.select_related('user').order_by('-created_at')

    search     = request.GET.get('q', '')
    domain     = request.GET.get('domain', '')
    level      = request.GET.get('level', '')
    success    = request.GET.get('success', '')
    start_date = request.GET.get('start_date', '')
    end_date   = request.GET.get('end_date', '')

    if search:
        corrections = corrections.filter(
            Q(user__phone_number__icontains=search) |
            Q(extracted_text__icontains=search) |
            Q(user_domain__icontains=search)
        )
    if domain:
        corrections = corrections.filter(user_domain__icontains=domain)
    if level:
        corrections = corrections.filter(user_level__icontains=level)
    if success == 'true':
        corrections = corrections.filter(success=True)
    elif success == 'false':
        corrections = corrections.filter(success=False)
    if start_date:
        try:
            corrections = corrections.filter(
                created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date()
            )
        except ValueError:
            pass
    if end_date:
        try:
            corrections = corrections.filter(
                created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    total_count   = CorrectionHistory.objects.count()
    success_count = CorrectionHistory.objects.filter(success=True).count()
    today_count   = CorrectionHistory.objects.filter(created_at__date=timezone.now().date()).count()

    domains = CorrectionHistory.objects.values_list('user_domain', flat=True).distinct().order_by('user_domain')
    levels  = CorrectionHistory.objects.values_list('user_level', flat=True).distinct().order_by('user_level')

    paginator = Paginator(corrections, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'custom_admin/admin/corrections.html', {
        'page_obj': page_obj,
        'total_count': total_count,
        'success_count': success_count,
        'today_count': today_count,
        'domains': domains,
        'levels': levels,
        'search': search,
        'domain': domain,
        'level': level,
        'success': success,
        'start_date': start_date,
        'end_date': end_date,
    })


@staff_required
def admin_correction_detail(request, pk):

    correction = get_object_or_404(CorrectionHistory.objects.select_related('user'), pk=pk)
    return render(request, 'custom_admin/admin/correction_detail.html', {
        'correction': correction,
    })


# =====================================================
# 💬 CONVERSATIONS CHATBOT
# =====================================================

@staff_required
def admin_conversations(request):

    sessions = ChatSession.objects.select_related('user').annotate(
        message_count=Count('messages')
    ).order_by('-created_at')

    search = request.GET.get('q', '')
    if search:
        sessions = sessions.filter(
            Q(user__phone_number__icontains=search) |
            Q(title__icontains=search)
        )

    total_sessions  = ChatSession.objects.count()
    total_messages  = ChatMessage.objects.count()
    active_sessions = ChatSession.objects.filter(is_active=True).count()
    today_sessions  = ChatSession.objects.filter(created_at__date=timezone.now().date()).count()

    paginator = Paginator(sessions, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'custom_admin/admin/conversations.html', {
        'page_obj': page_obj,
        'total_sessions': total_sessions,
        'total_messages': total_messages,
        'active_sessions': active_sessions,
        'today_sessions': today_sessions,
        'search': search,
    })


@staff_required
def admin_conversation_detail(request, session_id):

    session  = get_object_or_404(ChatSession.objects.select_related('user'), id=session_id)
    messages_qs = session.messages.order_by('created_at')
    return render(request, 'custom_admin/admin/conversation_detail.html', {
        'session': session,
        'messages': messages_qs,
    })


# =====================================================
# 💰 PAIEMENTS & REVENUS
# =====================================================

@staff_required
def admin_payments(request):

    transactions = Transaction.objects.select_related('user', 'pack').order_by('-created_at')

    search     = request.GET.get('q', '')
    tx_type    = request.GET.get('type', '')
    start_date = request.GET.get('start_date', '')
    end_date   = request.GET.get('end_date', '')

    if search:
        transactions = transactions.filter(
            Q(user__phone_number__icontains=search) |
            Q(pack__name__icontains=search)
        )
    if tx_type:
        transactions = transactions.filter(transaction_type=tx_type)
    if start_date:
        try:
            transactions = transactions.filter(
                created_at__date__gte=datetime.strptime(start_date, '%Y-%m-%d').date()
            )
        except ValueError:
            pass
    if end_date:
        try:
            transactions = transactions.filter(
                created_at__date__lte=datetime.strptime(end_date, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    now = timezone.now()

    total_revenue      = Transaction.objects.filter(payment_status='paid').aggregate(t=Sum('price_paid'))['t'] or 0
    this_month_revenue = Transaction.objects.filter(
        payment_status='paid',
        created_at__year=now.year, created_at__month=now.month
    ).aggregate(t=Sum('price_paid'))['t'] or 0
    total_tx  = Transaction.objects.filter(payment_status='paid').count()
    today_tx  = Transaction.objects.filter(payment_status='paid', created_at__date=now.date()).count()

    # Graphique : 6 derniers mois
    monthly_data = []
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        rev = Transaction.objects.filter(
            payment_status='paid',
            created_at__year=month_start.year,
            created_at__month=month_start.month
        ).aggregate(t=Sum('price_paid'))['t'] or 0
        monthly_data.append({
            'label': month_start.strftime('%b %Y'),
            'revenue': float(rev),
        })

    paginator = Paginator(transactions, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'custom_admin/admin/payments.html', {
        'page_obj': page_obj,
        'total_revenue': int(total_revenue),
        'this_month_revenue': int(this_month_revenue),
        'total_tx': total_tx,
        'today_tx': today_tx,
        'monthly_data': json.dumps(monthly_data),
        'search': search,
        'tx_type': tx_type,
        'start_date': start_date,
        'end_date': end_date,
    })


# =====================================================
# SUPPORT TICKETS
# =====================================================

@staff_required
def admin_support_tickets(request):
    tickets = SupportTicket.objects.select_related('user').prefetch_related('messages')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter == '1':
        tickets = tickets.filter(is_priority=True)

    # Stats rapides
    open_count = SupportTicket.objects.filter(status='open').count()
    inprogress_count = SupportTicket.objects.filter(status='in_progress').count()
    priority_count = SupportTicket.objects.filter(is_priority=True).exclude(status='closed').count()

    paginator = Paginator(tickets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'custom_admin/admin/support_tickets.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'open_count': open_count,
        'inprogress_count': inprogress_count,
        'priority_count': priority_count,
    })


@staff_required
def admin_support_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        action = request.POST.get('action', 'reply')
        if action == 'reply':
            content = request.POST.get('content', '').strip()
            if content:
                SupportMessage.objects.create(ticket=ticket, sender_type='admin', content=content)
                ticket.status = 'in_progress'
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, 'Réponse envoyée.')
        elif action == 'close':
            ticket.status = 'closed'
            ticket.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Ticket fermé.')
        elif action == 'reopen':
            ticket.status = 'open'
            ticket.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Ticket rouvert.')
        return redirect('custom_admin:support_ticket_detail', ticket_id=ticket_id)

    return render(request, 'custom_admin/admin/support_ticket_detail.html', {'ticket': ticket})


# =====================================================
# LANDING PAGE (PUBLIC)
# =====================================================

def landing_page(request):
    packs = Pack.objects.filter(is_active=True).order_by('price')
    site = SiteSettings.get_instance()
    return render(request, 'custom_admin/landing.html', {
        'packs': packs,
        'site': site,
    })
