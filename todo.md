# TODO — Corrections issues du rapport QA

Légende : 🔴 Critique · 🟠 Haut · 🟡 Moyen · 🟢 Bas

---

## BLOC 1 — Sécurité & Configuration ✅ TERMINÉ

- [x] 🔴 **Bug #1 · Bug #27 · Bug #28 — Sécuriser settings.py**
  - [x] Charger `SECRET_KEY` depuis `.env` (`os.environ.get('SECRET_KEY')`) — `settings.py`
  - [x] Passer `DEBUG` en variable d'env (`os.getenv('DEBUG', 'False') == 'True'`) — `settings.py`
  - [x] Corriger format `.env` (retirer guillemets/espaces parasites autour de `SECRET_KEY`)
  - [x] Ajouter `DEBUG=True` dans `.env` pour le dev local

- [x] 🔴 **Bug #1 — Supprimer l'OTP hardcodé**
  - [x] Remplacer `self.code = "123456"` par `self.code = str(random.randint(100000, 999999))` — `authentification/models.py:89`
  - [x] `import random` déjà présent dans le fichier
  - [x] Supprimer les `print(password)` et `print(pending_user.password)` — `authentification/views.py:81,121`

- [x] 🔴 **Bug #3 — Corriger la durée de vie des tokens JWT**
  - [x] Passer `ACCESS_TOKEN_LIFETIME` à `timedelta(minutes=30)` — `settings.py`
  - [x] Passer `REFRESH_TOKEN_LIFETIME` à `timedelta(days=7)` — `settings.py`
  - [x] Activer `ROTATE_REFRESH_TOKENS = True` et `BLACKLIST_AFTER_ROTATION = True`
  - [x] Ajouter `rest_framework_simplejwt.token_blacklist` dans `INSTALLED_APPS`
  - [x] Migrer la blacklist (`python manage.py migrate`) → 12 migrations appliquées

- [x] 🟠 **Bug #29 — Ajouter le rate limiting sur les endpoints auth**
  - [x] Créer `authentification/throttles.py` avec 4 classes (signup/otp/login/password_reset)
  - [x] Déclarer les rates dans `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']` — `settings.py`
  - [x] Ajouter `throttle_classes = [SignupRateThrottle]` sur `SignupRequestView`
  - [x] Ajouter `throttle_classes = [OTPRateThrottle]` sur `OTPVerificationView`
  - [x] Ajouter `throttle_classes = [LoginRateThrottle]` sur `LoginView`
  - [x] Ajouter `throttle_classes = [PasswordResetRateThrottle]` sur `PasswordResetRequestView`
  - [x] Rate limiting Django cache (5 tentatives / 5 min) sur `admin_login` — `custom_admin/views.py`

---

## BLOC 2 — Authentification & Sessions ✅ TERMINÉ

- [x] 🟡 **Bug #2 — Vérifier l'expiration du PendingUser**
  - [x] Appeler `pending_user.is_valid()` dans `OTPVerificationView` avant de valider l'OTP — `authentification/views.py`
  - [x] Si expiré : supprimer le PendingUser + retourner 400 `"Votre demande d'inscription a expiré. Veuillez recommencer l'inscription."`

- [x] 🟢 **Bug #4 — Endpoint logout côté serveur**
  - [x] Blacklist déjà activée dans Bloc 1 (`token_blacklist` + migration)
  - [x] Créer `LogoutView` (POST, IsAuthenticated) qui appelle `RefreshToken(token).blacklist()` — `authentification/views.py`
  - [x] Enregistrer l'endpoint `POST /api/auth/logout/` — `authentification/urls.py`
  - [x] Gérer `TokenError` → retourner 400 si token déjà expiré/invalide

- [x] 🟡 **Bug #31 — Gérer l'IntegrityError sur mise à jour de profil**
  - [x] `try/except IntegrityError` autour de `serializer.save()` dans `UpdateProfileView.put()` — `authentification/views.py`
  - [x] Retourne HTTP 400 : `"Ce numéro de téléphone est déjà utilisé par un autre compte."`

- [x] 🟡 **Bug #30 — Supprimer les print de données sensibles**
  - [x] Tous les `print()` supprimés de `authentification/views.py` (vérifié par grep — 0 résultat)

---

## BLOC 3 — Paiement & Abonnements ✅ TERMINÉ

- [x] 🔴 **Bug #11 — Sécuriser le webhook GeniusPay**
  - [x] `if not secret: return True` → `return False` dans `_verify_geniuspay_signature` — `subscriptions/views.py`
  - [x] `logger.error()` si secret absent (plus de `print`, trace dans les logs serveur)

- [x] 🔴 **Bug #10 — Activation webhook atomique**
  - [x] `with db_transaction.atomic()` autour de `transaction.save()` + `_activate_subscription()` — webhook
  - [x] Idem dans `check_payment_status` (2ème point d'activation)
  - [x] Si exception → `logger.error()` + retourne `activation_error` sans propager (GeniusPay attend toujours 200)

- [x] 🟠 **Bug #9 — Anti double débit**
  - [x] Avant appel GeniusPay, chercher `Transaction pending < 10 min` pour le même user+pack avec token_pay existant
  - [x] Si trouvée → retourner le `token_pay` existant sans créer de nouvelle transaction

- [x] 🟠 **Bug #5 — Race condition déduction quota**
  - [x] `deduct_image_correction()` → `update()` atomique avec `F('image_corrections_remaining') - 1` — `subscriptions/models.py`
  - [x] `deduct_chat_question()` → même pattern atomique
  - [x] `self.refresh_from_db()` après chaque update pour resynchroniser l'objet

- [x] 🟡 **Bug #12 — Éliminer les transactions zombies**
  - [x] Transaction créée APRÈS la réponse GeniusPay réussie (plus de zombie si API timeout/erreur)
  - [x] Mock mode : transaction créée directement avec le `token_pay` mock
  - [x] `logger.error()` remplace `print()` pour les erreurs GeniusPay

- [x] 🟡 **Bug #13 — Validation format numéro de téléphone**
  - [x] Regex `_PHONE_RE = re.compile(r'^\+[1-9]\d{6,14}$')` compilée au module — `subscriptions/views.py`
  - [x] Appliquée sur `phone_number` pour les packs payants → HTTP 400 si invalide

- [x] 🟢 **Bug #14 — Pack gratuit souscriptible plusieurs fois**
  - [x] Check existant `current_sub.pack.id == new_pack.id and not current_sub.is_expired()` couvre ce cas
  - [x] Pack gratuit wrappé dans `db_transaction.atomic()` pour cohérence

---

## BLOC 4 — Module Enseignant (classes) ✅ TERMINÉ

- [x] 🟠 **Bug #15 — Valider les champs numériques des devoirs**
  - [x] `coefficient > 0`, `max_score > 0`, `global_bonus >= 0`, `global_bonus <= max_score` — `classes/views.py`
  - [x] HTTP 400 avec message précis pour chaque cas (POST et PUT)

- [x] 🟠 **Bug #16 — Guard contre division par zéro dans les stats**
  - [x] Déjà couvert : `if a.max_score == 0: continue` dans `Student.average()`, `and a.max_score > 0` dans `classroom_stats`
  - [x] Bug #15 (max_score > 0) prévient l'injection de barèmes nuls

- [x] 🟡 **Bug #17 — Contrainte unique sur les élèves**
  - [x] `unique_together = ('classroom', 'first_name', 'last_name')` dans `Student.Meta` — `classes/models.py`
  - [x] Migration `0004_student_unique_together` créée et appliquée
  - [x] `IntegrityError` capturé dans `add_students()` → HTTP 409

- [x] 🟡 **Bug #18 — Valider les élèves avant bulk_create**
  - [x] Noms tronqués à 100 chars, `last_name` vide filtré
  - [x] `bulk_create(..., ignore_conflicts=True)` pour éviter les crashes sur doublons

- [x] 🟡 **Bug #19 — Valider le format des dates**
  - [x] `datetime.strptime(date, '%Y-%m-%d')` dans `assignments()` POST, `assignment_detail()` PUT, `attendance_sessions()` POST

- [x] 🟡 **Bug #20 — Valider le format de l'heure de présence**
  - [x] Regex `^\d{2}:\d{2}(:\d{2})?$` dans `attendance_sessions()` POST → HTTP 400

- [x] 🟡 **Bug #21 — Bloquer bonus > barème**
  - [x] `global_bonus > max_score` → HTTP 400 dans `assignments()` POST et `assignment_detail()` PUT

- [x] 🟡 **Bug #22 — Éviter les sessions de présence en doublon**
  - [x] Check `AttendanceSession.objects.filter(classroom, date, time).exists()` → HTTP 409 si doublon

- [x] 🟢 **Bug #32 — Retourner 0 plutôt que None pour les moyennes vides**
  - [x] `or 0` sur tous les retours `average()` et `class_average()` dans les réponses API
  - [x] `classroom_report`, `classroom_stats`, `student_stats`, ranking

---

## BLOC 5 — Traitement des images (correction IA) ✅ TERMINÉ

- [x] 🟡 **Bug #6 — Limiter la taille des images uploadées**
  - [x] Validation 10 MB dans `ProcessImageView` — `treatment/views.py`
  - [x] HTTP 400 : `"Fichier trop volumineux (max 10 Mo)."`

- [x] 🟡 **Bug #7 — Limiter la longueur du champ `infos`**
  - [x] Rejet `infos` > 2000 caractères — `treatment/views.py`
  - [x] HTTP 400 avec message clair

- [x] 🟢 **Bug #8 — Paginer l'historique des corrections**
  - [x] Pagination 20 items/page sur `HistoryView` — `treatment/views.py`
  - [x] Flutter `fetchCorrectionHistory` mis à jour pour la réponse paginée

---

## BLOC 6 — Dashboard Admin ✅ TERMINÉ

- [x] 🟡 **Bug #24 — Optimiser la liste des utilisateurs admin**
  - [x] `prefetch_related('subscriptions')` sur `admin_users` — `custom_admin/views.py`
  - [x] `per_page` par défaut passé à 50

- [x] 🟡 **Bug #25 — Valider le prix des packs dans l'admin**
  - [x] `price >= 0` dans `admin_pack_create` — `custom_admin/views.py`
  - [x] `price >= 0` dans `admin_pack_edit` — `custom_admin/views.py`
  - [x] HTTP 400 formulaire si valeur négative

- [x] 🟢 **Bug #26 — Confirmation avant suppression d'utilisateur**
  - [x] `GET admin_user_delete` → retourne stats cascade (classes, élèves, devoirs, abonnements, corrections)
  - [x] `POST admin_user_delete` → suppression effective
  - [x] Frontend peut afficher modal de confirmation avec les chiffres avant de confirmer

---

## BLOC 7 — UX (améliorations mobile + PDF) ✅ TERMINÉ (sauf UX #7)

- [x] 🟡 **UX #1 — Messages d'erreur OTP plus clairs**
  - [x] `PendingUser.DoesNotExist` → "Numéro introuvable. Veuillez recommencer l'inscription."
  - [x] `OTPCode.DoesNotExist` → "Code OTP incorrect."
  - [x] OTP expiré → "Code OTP expiré. Utilisez 'Renvoyer le code'..."
  - [x] Nouveau endpoint `POST /api/auth/otp/resend/` — `ResendOTPView` (AllowAny, throttlé)

- [x] 🟡 **UX #3 — Augmenter le timeout de paiement**
  - [x] `_maxAttempts = 40` (40 × 3s = 120s) — `payment_waiting_screen.dart`
  - [x] Message intermédiaire à 60s (tentative 20) : "Paiement en cours de traitement..."
  - [x] Fix bonus : `WillPopScope` → `PopScope`, BuildContext async gap corrigé

- [x] 🟡 **UX #5 — Afficher le quota restant AVANT l'upload**
  - [x] `_buildAnalyzeButton()` lit `SubscriptionProvider.subscription.remainingImages`
  - [x] Si quota = 0 : bouton remplacé par bannière rouge "Quota épuisé — Souscrivez à un pack"

- [x] 🟡 **UX #6 — Valider le format de `school_year`**
  - [x] Backend : regex `^\d{4}(-\d{4})?$` dans `classrooms()` POST et `classroom_detail()` PUT
  - [x] Flutter : validation dans `_save()` de `CreateClassroomScreen`

- [ ] 🟡 **UX #7 — Meilleur encodage des noms dans le PDF**
  - [ ] Nécessite l'ajout manuel d'un fichier TTF (ex: NotoSans.ttf) dans `assets/fonts/`
  - [ ] Charger via `pw.Font.ttf(await rootBundle.load('assets/fonts/NotoSans.ttf'))`
  - [ ] Mettre à jour `pubspec.yaml` avec l'entrée `assets`

- [x] 🟢 **UX #10 — Notification push Firebase après activation abonnement**
  - [x] `fcm_token` ajouté sur `CustomUser` + migration `0004_add_fcm_token`
  - [x] `POST /api/auth/fcm-token/` — `UpdateFCMTokenView` (IsAuthenticated)
  - [x] `_send_push_notification()` appelé dans `_activate_subscription()` — silencieux si non configuré
  - [x] `FIREBASE_CREDENTIALS_PATH` dans `.env` pour activer (optionnel)

---

## Récapitulatif global

| Bloc | Statut | Tâches |
|------|--------|--------|
| Bloc 1 — Sécurité & Config | ✅ Terminé | 4/4 |
| Bloc 2 — Auth & Sessions | ✅ Terminé | 4/4 |
| Bloc 3 — Paiement | ✅ Terminé | 6/6 |
| Bloc 4 — Module Enseignant | ✅ Terminé | 9/9 |
| Bloc 5 — Traitement images | ✅ Terminé | 3/3 |
| Bloc 6 — Dashboard Admin | ✅ Terminé | 3/3 |
| Bloc 7 — UX mobile + PDF | 🔶 5/6 (UX #7 manuel) | 5/6 |

### Seul item restant

- [ ] 🟡 **UX #7 — Police TTF dans le PDF bulletin**
  - Ajouter `NotoSans.ttf` (ou DejaVu) dans `assets/fonts/` du projet Flutter
  - Déclarer dans `pubspec.yaml` → `flutter: assets: [assets/fonts/NotoSans.ttf]`
  - Dans `pdf_report_service.dart` : `final font = pw.Font.ttf(await rootBundle.load('assets/fonts/NotoSans.ttf'));`
  - Passer `font:` à tous les `pw.TextStyle(...)` du service

---

*Mis à jour le 2026-03-25 — 38/39 corrections appliquées*
