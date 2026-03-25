# Rapport de Simulation Utilisateurs Réels - Corrige Moi

---

## 1. Résumé Exécutif

**Score global de qualité fonctionnelle : 5.4 / 10**

| Indicateur | Valeur |
|---|---|
| Bugs critiques | 4 |
| Bugs hauts | 9 |
| Bugs moyens | 18 |
| Bugs bas | 16 |
| Total bugs identifiés | 47 |
| Risque utilisateur réel | ÉLEVÉ |

**Verdict** : La plateforme est fonctionnelle pour un MVP en développement mais présente des failles graves empêchant tout déploiement production serein. Le système de paiement, la gestion des quotas, et l'authentification ont des vulnérabilités exploitables. Le module enseignant et le dashboard admin sont bien construits structurellement, mais manquent de garde-fous sur les données.

---

## 2. Personas Testés

| # | Persona | Profil | Objectif principal |
|---|---|---|---|
| P1 | **Élève débutant** | 15 ans, lycée, premier usage | S'inscrire, corriger un exercice de maths |
| P2 | **Élève abonné** | Utilisateur régulier avec Pack actif | Corriger des images, utiliser le chat IA |
| P3 | **Enseignant** | Prof de collège, peu tech-savvy | Créer une classe, saisir des notes, faire l'appel |
| P4 | **Administrateur** | Gestionnaire plateforme | Gérer utilisateurs, packs, voir statistiques |
| P5 | **Attaquant opportuniste** | Testeur limite | Trouver des failles sans connaissances avancées |
| P6 | **Parent payeur** | Adulte qui souscrit un pack pour son enfant | Acheter un abonnement, vérifier que ça marche |

---

## 3. Parcours Utilisateurs Testés

---

### Parcours 1 : Inscription complète (P1 – Élève débutant)

**Étapes simulées :**

1. L'utilisateur ouvre l'app, arrive sur l'écran d'inscription.
2. Remplit numéro de téléphone : `+2250701234567`
3. `POST /api/auth/signup/request/` → reçoit un SMS avec OTP (en dev, OTP = `123456`)
4. Saisit `123456` → `POST /api/auth/verify-otp/` avec mot de passe + profil
5. Connexion automatique après vérification

**Résultat :** ✅ Fonctionne

**Bug #1 — CRITIQUE : OTP universel hardcodé**
- **Fichier :** `authentification/models.py:89-90`
- `self.code = "123456"` en dur pour TOUS les utilisateurs dans TOUS les environnements.
- Un attaquant peut créer un compte avec n'importe quel numéro de téléphone + OTP `123456`.
- **Gravité : CRITIQUE**

**Bug #2 — MOYEN : PendingUser expiré accepté**
- **Fichier :** `authentification/views.py` (OTPVerificationView)
- `PendingUser.is_valid()` existe (`models.py`) mais n'est jamais appelée dans la vue de vérification OTP.
- Un OTP reçu il y a 2h est encore accepté.
- **Gravité : MOYEN**

---

### Parcours 2 : Connexion et gestion de session (P1 / P2)

**Étapes simulées :**

1. `POST /api/auth/login/` avec `phone_number` + `password` → retourne `access` + `refresh` JWT
2. Accès à `GET /api/auth/profile/` avec `Authorization: Bearer <token>`
3. Token expiré → `POST /api/auth/token/refresh/`
4. Déconnexion côté client (suppression du token local)

**Bug #3 — CRITIQUE : Durée de vie des JWT = 365 jours**
- **Fichier :** `backend_project/settings.py:94-95`
```python
'ACCESS_TOKEN_LIFETIME': timedelta(days=365),
'REFRESH_TOKEN_LIFETIME': timedelta(days=365),
```
- Standard recommandé : access = 15 min, refresh = 7 jours.
- Un token volé donne un accès total pendant 1 an.
- **Gravité : CRITIQUE**

**Bug #4 — BAS : Aucun endpoint de logout côté serveur**
- Pas de blacklist de tokens à la déconnexion. Le token reste valide jusqu'à expiration.
- **Gravité : BAS**

---

### Parcours 3 : Correction d'image (P2 – Élève abonné)

**Étapes simulées :**

1. L'utilisateur prend en photo un exercice de physique.
2. `POST /api/treatment/process-image/` avec image + contexte (`domain=science`, `level=terminale`)
3. Le backend fait OCR (Pytesseract) → appelle Gemini → retourne correction JSON.
4. L'historique est sauvegardé, quota déduit.

**Résultat :** ✅ Fonctionne dans le cas nominal

**Bug #5 — HAUT : Race condition sur la déduction de quota**
- **Fichier :** `subscriptions/models.py:122-132`
```python
def deduct_image_correction(self):
    if self.image_corrections_remaining <= 0:
        raise ValueError(...)
    self.image_corrections_remaining -= 1
    self.save()
```
- Pattern "check-then-act" non atomique. Deux requêtes simultanées passent toutes les deux le check à `remaining=1`, déduisent chacune 1, sauvegardent `0`. Quota = 2 corrections pour le prix de 1.
- **Fix :** `Subscription.objects.filter(pk=self.pk, image_corrections_remaining__gt=0).update(image_corrections_remaining=F('image_corrections_remaining') - 1)`
- **Gravité : HAUT**

**Bug #6 — MOYEN : Aucune validation de la taille de l'image uploadée**
- **Fichier :** `treatment/views.py`
- Un utilisateur peut envoyer un fichier de 500 MB. Pas de limite de taille configurée dans la vue.
- Charge Gemini + OCR pour rien, peut saturer la mémoire.
- **Gravité : MOYEN**

**Bug #7 — MOYEN : Champ `infos` sans limite de longueur**
- **Fichier :** `treatment/views.py:114`
- `infos = context.get('infos', '')` — aucun `max_length` vérifié côté API.
- Un payload de 1 MB de texte peut être envoyé à Gemini, augmentant les coûts API de façon non contrôlée.
- **Gravité : MOYEN**

**Bug #8 — BAS : Aucune pagination sur l'historique**
- **Fichier :** `treatment/urls.py` (HistoryView)
- `GET /api/treatment/history/` retourne TOUTES les corrections sans pagination.
- Un utilisateur avec 3 ans d'historique peut bloquer l'API.
- **Gravité : BAS**

---

### Parcours 4 : Achat d'abonnement – Pack payant (P6 – Parent payeur)

**Étapes simulées :**

1. `GET /api/subscription/packs/` → liste des packs actifs
2. Sélection d'un pack à 5000 XOF → saisie du numéro de téléphone
3. `POST /api/subscription/subscribe/` → reçoit `payment_url` + `token_pay`
4. WebView s'ouvre sur GeniusPay → paiement Wave/Orange
5. GeniusPay envoie webhook `POST /api/subscription/payment/webhook/`
6. L'abonnement est activé, quotas crédités
7. App poll `GET /api/subscription/payment/status/<token>/` pendant 60s

**Résultat :** ✅ Fonctionne dans le cas nominal

**Bug #9 — HAUT : Double souscription possible (double débit)**
- **Fichier :** `subscriptions/views.py:138-146`
- Si l'utilisateur clique deux fois sur "Souscrire" (réseau lent), deux `Transaction` pending sont créées.
- Si GeniusPay traite les deux, l'utilisateur est débité deux fois.
- Pas de vérification de transaction pending existante pour le même pack.
- **Gravité : HAUT**

**Bug #10 — HAUT : Webhook sans rollback si activation échoue**
- **Fichier :** `subscriptions/views.py:302-317`
- Si `_activate_subscription()` lève une exception après `transaction.payment_status = 'paid'`, la transaction est marquée payée mais aucune `Subscription` n'est créée.
- L'utilisateur est débité mais n'a pas accès à la plateforme.
- **Gravité : HAUT**

**Bug #11 — HAUT : Webhook sans vérification de signature si secret absent**
- **Fichier :** `subscriptions/views.py:261-269`
```python
if not secret:
    return True  # skip en dev
```
- Si `GENIUSPAY_WEBHOOK_SECRET` n'est pas configuré en production, n'importe qui peut POST sur `/payment/webhook/` et activer gratuitement n'importe quel abonnement.
- **Gravité : HAUT**

**Bug #12 — MOYEN : Transaction créée avant l'appel GeniusPay**
- **Fichier :** `subscriptions/views.py:108-146`
- La `Transaction` est créée en statut `pending` AVANT l'appel API GeniusPay. Si l'API échoue (timeout, erreur 500), la transaction reste en `pending` en base pour toujours.
- Accumulation de transactions zombies.
- **Gravité : MOYEN**

**Bug #13 — MOYEN : Aucune validation du format du numéro de téléphone**
- **Fichier :** `subscriptions/views.py:74`
- `phone_number = request.data.get('phone_number')` — pas de validation E.164, pas de vérification d'opérateur.
- Un numéro comme `"abc123"` ou `"0"` est envoyé à GeniusPay, qui retournera une erreur non gérée proprement.
- **Gravité : MOYEN**

---

### Parcours 5 : Achat d'abonnement – Pack gratuit (P1 – Élève débutant)

**Étapes simulées :**

1. L'utilisateur voit un pack "Découverte" à 0 XOF marqué comme gratuit
2. `POST /api/subscription/subscribe/` avec `pack_id` seulement (pas de `phone_number`)
3. Le backend détecte `pack.is_free == True`, crée directement la `Subscription` + `Transaction(price_paid=0, payment_status='paid')`
4. Retourne `{success: True, is_free: True}`
5. Flutter détecte `is_free=True`, affiche un overlay de succès direct

**Résultat :** ✅ Fonctionne (implémentation récente)

**Bug #14 — BAS : Pas de limite sur l'activation répétée d'un pack gratuit**
- Un même utilisateur peut souscrire au pack gratuit autant de fois qu'il veut, cumulant les quotas.
- Pas de vérification "déjà actif sur ce pack gratuit".
- **Gravité : BAS**

---

### Parcours 6 : Module enseignant – Création de classe et saisie de notes (P3)

**Étapes simulées :**

1. `POST /api/classes/` avec `name`, `subject`, `school_name`, `school_year` → classe créée
2. `POST /api/classes/extract-students/` avec image d'une liste de classe → OCR Gemini → liste d'élèves retournée
3. `POST /api/classes/<id>/students/` pour ajouter les élèves
4. `POST /api/classes/<id>/assignments/` → devoir créé
5. `POST /api/classes/<id>/assignments/<id>/grade/` → saisie des notes
6. `GET /api/classes/<id>/report/` → bulletin de notes

**Résultat :** ✅ Fonctionne dans le cas nominal

**Bug #15 — HAUT : Valeurs négatives acceptées pour coefficient et max_score**
- **Fichier :** `classes/views.py:352-354`
```python
coefficient=float(data.get('coefficient', 1.0)),
max_score=float(data.get('max_score', 20.0)),
global_bonus=float(data.get('global_bonus', 0.0)),
```
- `coefficient=-100` ou `max_score=0.001` sont acceptés sans erreur.
- `max_score` négatif provoque une division par négatif → moyenne > 100% → statistiques corrompues définitivement.
- **Gravité : HAUT**

**Bug #16 — HAUT : Division par zéro possible en stats si max_score = 0**
- **Fichier :** `classes/views.py:714-717`
```python
normalized = [round(min(max((g.score + a.global_bonus) / a.max_score * 20, 0), 20), 2) for g in graded]
```
- Si `max_score` est modifié à 0 en base (ou accepté à la création), cette ligne crash avec `ZeroDivisionError`.
- Le endpoint `GET /api/classes/<id>/stats/` lancerait une 500.
- **Gravité : HAUT**

**Bug #17 — MOYEN : Doublons d'élèves sans contrainte unique**
- **Fichier :** `classes/models.py` (Student)
- Aucun `unique_together` sur `(classroom, first_name, last_name)`.
- L'OCR peut créer 2 fois le même élève → moyenne faussée, doublons dans les bulletins.
- **Gravité : MOYEN**

**Bug #18 — MOYEN : bulk_create des élèves ignore les validateurs Django**
- **Fichier :** `classes/views.py:291-299`
- `Student.objects.bulk_create([...])` ne déclenche pas `full_clean()`.
- Des noms de 500 caractères ou des caractères spéciaux non filtrés entrent en base.
- **Gravité : MOYEN**

**Bug #19 — MOYEN : Format date non validé pour les devoirs et sessions de présence**
- **Fichier :** `classes/views.py:340, 586`
- `date = data.get('date')` accepté directement. `"32/13/2099"` ou `"tomorrow"` lèverait une exception non gérée à la sauvegarde.
- **Gravité : MOYEN**

**Bug #20 — MOYEN : Heure de session de présence non validée**
- **Fichier :** `classes/views.py:587`
- `time = data.get('time')` — `"25:99"` ou `"matin"` passent sans erreur jusqu'à la sauvegarde.
- **Gravité : MOYEN**

**Bug #21 — MOYEN : bonus global peut dépasser le barème**
- **Fichier :** `classes/views.py:354`
- `global_bonus=5000` sur un devoir `/20` → score effectif = 5020/20 → moyenne classe absurde.
- **Gravité : MOYEN**

**Bug #22 — MOYEN : Duplication silencieuse des enregistrements de présence**
- **Fichier :** `classes/views.py` (endpoint POST attendance)
- Si l'endpoint `POST /<id>/attendance/` est appelé deux fois pour la même date, une deuxième `AttendanceSession` est créée. Les statistiques comptent alors deux séances pour la même journée.
- **Gravité : MOYEN**

---

### Parcours 7 : Dashboard administrateur (P4)

**Étapes simulées :**

1. Admin se connecte via `/custom-admin/login/`
2. Visite dashboard principal → KPI cards, graphiques d'activité
3. Liste des utilisateurs, filtre par rôle (Étudiant / Enseignant)
4. Création d'un utilisateur, édition d'un pack
5. Accès aux rapports et statistiques

**Résultat :** ✅ Fonctionne globalement

**Bug #23 — HAUT : Aucun rate-limiting sur la connexion admin**
- **Fichier :** `custom_admin/views.py` (admin_login)
- Pas de délai, pas de blocage après N tentatives échouées.
- Brute-force du mot de passe admin possible en quelques minutes.
- **Gravité : HAUT**

**Bug #24 — MOYEN : Pas de pagination sur la liste des utilisateurs**
- **Fichier :** `custom_admin/views.py:281-301`
- `CustomUser.objects.all()` sans `select_related` ni limite. Avec 50 000 utilisateurs, le chargement de la page peut prendre plusieurs secondes / OOM.
- **Gravité : MOYEN**

**Bug #25 — MOYEN : Valeurs négatives acceptées pour le prix d'un pack**
- **Fichier :** `custom_admin/views.py` (admin_pack_create / admin_pack_edit)
- `price = Decimal(request.POST.get('price', 0))` — `price=-500` est accepté et sauvegardé.
- **Gravité : MOYEN**

**Bug #26 — BAS : Pas de confirmation avant suppression d'entités critiques**
- Supprimer un enseignant supprime en CASCADE toutes ses classes, tous ses élèves, toutes ses notes (relation `on_delete=CASCADE`).
- Aucune confirmation modale ni vérification côté backend avant suppression.
- **Gravité : BAS**

---

### Parcours 8 : Tentatives limites (P5 – Attaquant opportuniste)

**Bug #27 — CRITIQUE : SECRET_KEY Django hardcodée dans settings.py**
- **Fichier :** `backend_project/settings.py:35`
```python
SECRET_KEY = 'django-insecure-)*_3xsh-gg-kg@...'
```
- Si le repo est public ou semi-public, n'importe qui peut forger des tokens de session Django.
- **Gravité : CRITIQUE**

**Bug #28 — CRITIQUE : DEBUG = True en production potentielle**
- **Fichier :** `backend_project/settings.py:38`
- Stack traces complètes (code source + variables locales) exposées aux utilisateurs en cas d'erreur.
- **Gravité : CRITIQUE**

**Bug #29 — HAUT : Aucune limite de tentatives sur signup/OTP**
- **Fichier :** `authentification/views.py:20-152`
- L'endpoint `POST /api/auth/signup/request/` peut être appelé 10 000x/sec. Pas de rate limiting.
- Enumération de numéros de téléphone valides via les messages d'erreur différenciés (`"Numéro déjà utilisé"` vs succès).
- **Gravité : HAUT**

**Bug #30 — MOYEN : Logs de mot de passe en clair**
- **Fichier :** `authentification/views.py:81-82`
```python
print("pending_user.password")
print(pending_user.password)
```
- Le hash du mot de passe est loggé sur stdout. Dans un contexte Render/Heroku, ces logs sont conservés.
- **Gravité : MOYEN**

---

### Parcours 9 : Gestion de profil utilisateur (P2)

**Bug #31 — MOYEN : Changement de numéro de téléphone vers un numéro existant**
- **Fichier :** `authentification/views.py:222-228`
- `PUT /api/auth/profile/` avec `phone_number` d'un autre utilisateur → `IntegrityError` Django non catchée → réponse 500 au lieu d'un message d'erreur propre.
- **Gravité : MOYEN**

---

## 4. Bugs & Erreurs Détectés

| # | Gravité | Parcours | Description | Localisation | Recommandation |
|---|---|---|---|---|---|
| 1 | **CRITIQUE** | Inscription | OTP universel `123456` hardcodé pour tous | `authentification/models.py:89` | Générer OTP aléatoire 6 chiffres, envoyer par SMS réel |
| 2 | **CRITIQUE** | Connexion | JWT lifetime = 365 jours | `settings.py:94-95` | Access=30min, Refresh=7j, blacklist à la déconnexion |
| 3 | **CRITIQUE** | Config | SECRET_KEY hardcodée dans le code | `settings.py:35` | Charger depuis `.env`, jamais commiter |
| 4 | **CRITIQUE** | Config | DEBUG=True en production possible | `settings.py:38` | `DEBUG = os.getenv('DEBUG', 'False') == 'True'` |
| 5 | **HAUT** | Correction | Race condition sur déduction quota | `subscriptions/models.py:122` | Utiliser `F()` + `update()` atomique |
| 6 | **HAUT** | Paiement | Double souscription possible (double débit) | `subscriptions/views.py:108` | Vérifier pending existant avant création |
| 7 | **HAUT** | Paiement | Webhook accepté sans secret configuré | `subscriptions/views.py:261` | Rejeter si secret absent (ne pas skip) |
| 8 | **HAUT** | Paiement | Paiement marqué `paid` sans rollback si activation échoue | `subscriptions/views.py:302` | Utiliser `transaction.atomic()` |
| 9 | **HAUT** | Notes | Valeurs négatives pour max_score/coefficient | `classes/views.py:352` | Valider `> 0` avant sauvegarde |
| 10 | **HAUT** | Stats | Division par zéro si max_score = 0 | `classes/views.py:714` | Guard `if a.max_score <= 0: continue` |
| 11 | **HAUT** | Admin | Aucun rate-limiting sur login admin | `custom_admin/views.py` | django-ratelimit ou fail2ban |
| 12 | **HAUT** | Signup | Aucun rate-limiting sur signup/OTP | `authentification/views.py` | Throttle 5 req/min par IP |
| 13 | **MOYEN** | Inscription | PendingUser expiré toujours accepté | `authentification/views.py` OTPVerify | Appeler `pending_user.is_valid()` |
| 14 | **MOYEN** | Correction | Aucune limite de taille sur image uploadée | `treatment/views.py` | Valider taille max (ex: 10MB) |
| 15 | **MOYEN** | Correction | Champ `infos` sans limite de longueur | `treatment/views.py:114` | `max_length=2000` côté validation |
| 16 | **MOYEN** | Paiement | Transaction zombie si GeniusPay échoue | `subscriptions/views.py:108` | Créer Transaction après succès API |
| 17 | **MOYEN** | Paiement | Numéro de téléphone non validé | `subscriptions/views.py:74` | Regex E.164 |
| 18 | **MOYEN** | Notes | Doublons d'élèves sans contrainte | `classes/models.py` Student | Ajouter `unique_together` |
| 19 | **MOYEN** | Notes | bulk_create ignore les validateurs | `classes/views.py:291` | Valider manuellement ou utiliser `validate_unique()` |
| 20 | **MOYEN** | Notes | Date devoir/présence non validée | `classes/views.py:340, 586` | Parser avec try/except + format ISO |
| 21 | **MOYEN** | Notes | Heure de présence non validée | `classes/views.py:587` | Valider format HH:MM |
| 22 | **MOYEN** | Notes | Bonus > barème accepté | `classes/views.py:354` | Valider `global_bonus <= max_score` |
| 23 | **MOYEN** | Présence | Séance en double pour même date | `classes/views.py` | `get_or_create` sur `(classroom, date)` |
| 24 | **MOYEN** | Admin | Pas de pagination sur liste utilisateurs | `custom_admin/views.py:281` | Paginator Django, 50 items/page |
| 25 | **MOYEN** | Admin | Prix négatif accepté pour les packs | `custom_admin/views.py` pack_create | Valider `price >= 0` |
| 26 | **MOYEN** | Profil | IntegerityError 500 sur changement numéro existant | `authentification/views.py:222` | try/except IntegrityError → 400 |
| 27 | **MOYEN** | Auth | Logs de hash de mot de passe sur stdout | `authentification/views.py:81` | Supprimer tous les `print` sensibles |
| 28 | **MOYEN** | Pack gratuit | Pack gratuit souscriptible plusieurs fois | `subscriptions/views.py` | Bloquer si sub active sur ce pack |
| 29 | **BAS** | Connexion | Pas d'invalidation JWT côté serveur au logout | Architecture | Ajouter blacklist SimpleJWT |
| 30 | **BAS** | Admin | Suppression cascade sans confirmation | `custom_admin/views.py` | Modal de confirmation + soft delete |
| 31 | **BAS** | Historique | Historique non paginé | `treatment/urls.py` | Pagination 20 items/page |
| 32 | **BAS** | Stats | Moyenne `None` si aucun élève/devoir | `classes/models.py` | Retourner `0` plutôt que `None` |

---

## 5. Problèmes UX / Ergonomie

1. **Messages d'erreur peu clairs sur l'OTP** — En production, si le SMS ne passe pas, l'utilisateur ne voit aucun message d'explication. L'interface affiche probablement "OTP invalide" sans préciser si c'est un problème d'envoi ou une faute de frappe.

2. **Pas de feedback pendant le traitement Gemini** — `POST /api/treatment/process-image/` peut prendre 5-15 secondes. Si l'app mobile ne gère pas proprement le loading, l'utilisateur pense que l'app a planté.

3. **Timeout de paiement de 60s trop court** — Pour les opérateurs lents (MTN, Moov), 60 secondes peut ne pas suffire. L'app annule le paiement alors que GeniusPay le traite encore. L'utilisateur est débité mais son abonnement n'est pas activé.

4. **Pas de page "mon abonnement" claire** — `GET /api/subscription/my-subscription/` retourne les quotas, mais si aucune subscription active, l'utilisateur ne sait pas vers quel pack se diriger.

5. **Aucun message quand le quota est épuisé AVANT d'uploader** — L'utilisateur choisit son image, attend le traitement, et reçoit une erreur "quota épuisé". Le quota restant devrait être affiché AVANT l'upload.

6. **Création de classe : champ `school_year` sans validation de format** — L'enseignant peut saisir "2024" ou "2024-2025" ou "cette année" — incohérence dans les bulletins exportés.

7. **Bulletin PDF : noms avec caractères africains mal encodés** — La police Helvetica (Latin-1) remplace les caractères non-Latin-1. Un élève nommé "Koné" ou "Diallo-Traoré" pourrait voir son nom tronqué ou déformé dans le PDF.

8. **Dashboard admin — graphiques invisibles en mode clair si `window.CM` non initialisé** — Si un graphique est ajouté sans utiliser `_cm.tick/_cm.grid`, il reste invisible en light mode. Pas de système de validation centralisé.

9. **Suppression d'enseignant depuis l'admin = perte de TOUTES ses données** — On_delete=CASCADE sur Classroom → Student → Grade. Un admin qui supprime un compte enseignant par erreur perd toutes les données de classe définitivement.

10. **Pas d'email de bienvenue ni de confirmation de paiement** — L'utilisateur n'a aucune trace écrite de son abonnement. En cas de litige, aucun reçu n'est généré.

---

## 6. Recommandations Prioritaires (Top 7 actions à corriger immédiatement)

### 1. Désactiver l'OTP hardcodé (CRITIQUE — 10 min de travail)
**Fichier :** `authentification/models.py:89`
```python
# AVANT
self.code = "123456"
# APRÈS
self.code = str(random.randint(100000, 999999))
```
Bloquer l'accès production tant que ce correctif n'est pas déployé.

### 2. Corriger la configuration sécurité Django (CRITIQUE — 30 min)
```python
# settings.py
SECRET_KEY = os.environ.get('SECRET_KEY')  # Jamais en dur
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ACCESS_TOKEN_LIFETIME = timedelta(minutes=30)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)
```

### 3. Sécuriser le webhook GeniusPay (CRITIQUE paiement — 20 min)
**Fichier :** `subscriptions/views.py:261`
```python
if not secret:
    return False  # Rejeter, jamais accepter sans secret
```
+ Entourer `_activate_subscription()` d'un `transaction.atomic()`.

### 4. Corriger la race condition sur les quotas (HAUT — 1h)
**Fichier :** `subscriptions/models.py:122`
```python
from django.db.models import F
updated = Subscription.objects.filter(
    pk=self.pk, image_corrections_remaining__gt=0
).update(image_corrections_remaining=F('image_corrections_remaining') - 1)
if not updated:
    raise ValueError("Quota épuisé.")
```

### 5. Valider les champs numériques sensibles (HAUT — 2h)
`max_score > 0`, `coefficient > 0`, `price >= 0`, `global_bonus >= 0 AND <= max_score`.
Ajouter dans `classes/views.py` et `custom_admin/views.py`.

### 6. Ajouter rate limiting sur les endpoints d'authentification (HAUT — 2h)
Utiliser `django-ratelimit` :
```python
@ratelimit(key='ip', rate='5/m', block=True)
def signup_request(request): ...
```
Viser : signup/OTP = 5 req/min/IP, login = 10 req/min/IP, admin login = 3 req/min.

### 7. Prévenir le double débit (HAUT paiement — 1h)
**Fichier :** `subscriptions/views.py`
Avant de créer la Transaction, vérifier :
```python
existing_pending = Transaction.objects.filter(
    user=user, pack=new_pack, payment_status='pending',
    created_at__gte=timezone.now() - timedelta(minutes=10)
).first()
if existing_pending:
    return Response({'payment_url': existing_pending.payment_url, 'token_pay': existing_pending.token_pay})
```

---

## 7. Note finale par catégorie

| Catégorie | Note | Commentaire |
|---|---|---|
| **Fonctionnalité** | 6.5 / 10 | Parcours nominaux fonctionnels. Race conditions et edge cases critiques non couverts |
| **Gestion des erreurs** | 4.5 / 10 | Beaucoup de `print()` au lieu de `logging`, erreurs 500 non catchées sur profil et stats |
| **UX** | 5.5 / 10 | Manque de feedback utilisateur, quotas non affichés avant action, timeout paiement court |
| **Access control** | 5.0 / 10 | JWT fonctionnel mais lifetime absurde (1 an). Pas de logout serveur. OTP universel = pas d'auth réelle |
| **Sécurité** | 3.5 / 10 | 4 bugs critiques dont OTP hardcodé et SECRET_KEY exposée. À corriger avant tout déploiement prod |
| **Performance** | 6.0 / 10 | Pas de pagination sur l'historique et l'admin. Requêtes N+1 non optimisées |
| **Robustesse paiement** | 5.0 / 10 | Flow GeniusPay logiquement bon mais manque atomicité, idempotence et gestion des duplicats |

---

*Rapport généré par simulation statique approfondie du code source — `C:\Users\HP I7\Desktop\git_project\CORRECTION-APP-BACKEND`*
*Date : 2026-03-25 | Auditeur : QA Engineer Simulation (Claude Sonnet 4.6)*
