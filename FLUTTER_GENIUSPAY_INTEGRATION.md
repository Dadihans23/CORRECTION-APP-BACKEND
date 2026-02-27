# Intégration Paiement GeniusPay — Flutter (Corrige Moi)

> Document à usage du développeur Flutter.
> Dernière mise à jour : 27/02/2026 — v1.1

---

## 1. Vue d'ensemble

Le système de paiement repose sur **GeniusPay** (`pay.genius.ci`), une passerelle Mobile Money pour l'Afrique de l'Ouest (Wave, Orange Money, MTN Money, Moov).

### Flow complet

```
App Flutter                     Backend Django              GeniusPay (pay.genius.ci)
    │                                │                          │
    ├─ POST /subscribe/ ────────────►│                          │
    │  { pack_id, phone_number }     │                          │
    │                                ├─ POST /payments ────────►│
    │                                │◄── { checkout_url, ref }─┤
    │◄── { payment_url, token_pay } ─┤                          │
    │                                │                          │
    ├─ Ouvre payment_url en WebView ────────────────────────────►│
    │                                │                          │ (user choisit
    │                                │                          │  Wave/Orange/MTN
    │                                │                          │  et paie)
    │  [poll toutes les 3s]          │                          │
    ├─ GET /payment/status/{token}/ ►│                          │
    │                                ├─ GET /payments/{ref} ───►│
    │                                │◄── { status: completed } ┤
    │◄── { payment_status: "paid" } ─┤                          │
    │                                │                          │
    ├─ Ferme WebView                 │                          │
    ├─ Rafraîchit subscription       │                          │
    └─ Affiche écran succès          │                          │
```

> **Comment ça marche** : GeniusPay génère une page de checkout hébergée (`checkout_url`) où l'utilisateur choisit lui-même son moyen de paiement (Wave, Orange, MTN…). Le backend poll GeniusPay pour récupérer le statut en temps réel.

### Statuts possibles du paiement

| Valeur      | Signification                                    |
|-------------|--------------------------------------------------|
| `pending`   | Paiement initié, en attente de l'action utilisateur |
| `paid`      | Paiement confirmé → abonnement activé             |
| `failed`    | Échec technique                                  |
| `cancelled` | Annulé par l'utilisateur ou expiré               |

---

## 2. Endpoints API

### Base URL

```
Développement : http://172.20.10.2:8000/api/
Production    : https://correction-app-backend.onrender.com/api/
```

Toutes les requêtes authentifiées nécessitent le header :
```
Authorization: Bearer <access_token>
```

---

### 2.1 Initier un paiement

```
POST /subscription/subscribe/
Authorization: Bearer <token>
Content-Type: application/json
```

**Body :**
```json
{
  "pack_id": 1,
  "phone_number": "0701234567",
  "return_url": "corrigemoi://payment-success",
  "error_url": "corrigemoi://payment-error"
}
```

| Champ          | Type   | Requis | Description                              |
|----------------|--------|--------|------------------------------------------|
| `pack_id`      | int    | ✓      | ID du pack sélectionné                   |
| `phone_number` | string | ✓      | Numéro Mobile Money de l'utilisateur     |
| `return_url`   | string |        | URL de retour après paiement réussi      |
| `error_url`    | string |        | URL de retour après échec                |

**Réponse succès (200) :**
```json
{
  "success": true,
  "message": "Paiement initié. Redirigez l'utilisateur vers payment_url.",
  "payment_url": "https://pay.genius.ci/checkout/MTX-A1B2C3D4E5",
  "token_pay": "MTX-A1B2C3D4E5",
  "pack": "Pack Essentiel",
  "amount": "2000"
}
```

> **Note** : `payment_url` pointe vers la **page de checkout GeniusPay** hébergée sur `pay.genius.ci`. L'utilisateur y choisira son moyen de paiement.

**Réponses erreur :**
```json
{ "success": false, "message": "Vous êtes déjà abonné à ce pack." }
{ "success": false, "message": "pack_id et phone_number sont requis." }
{ "success": false, "message": "Erreur de connexion au service de paiement." }
```

**Actions Flutter après succès :**
1. Récupérer `payment_url` et `token_pay`
2. Ouvrir `payment_url` dans un WebView
3. Démarrer le polling sur `token_pay`

---

### 2.2 Vérifier le statut d'un paiement (polling)

```
GET /subscription/payment/status/{token_pay}/
Authorization: Bearer <token>
```

**Réponse (200) :**
```json
{
  "success": true,
  "payment_status": "paid",
  "pack": "Pack Essentiel",
  "amount": "2000"
}
```

**Valeurs de `payment_status` :**

| Valeur      | Action Flutter                                           |
|-------------|----------------------------------------------------------|
| `pending`   | Continuer le polling                                     |
| `paid`      | Arrêter poll → rafraîchir providers → afficher succès    |
| `failed`    | Arrêter poll → afficher dialogue erreur + réessayer      |
| `cancelled` | Arrêter poll → afficher dialogue annulation + réessayer  |

**Logique de polling recommandée :**
- Intervalle : toutes les **3 secondes**
- Durée max : **2 minutes** (40 tentatives)
- Après timeout → arrêter silencieusement (l'utilisateur peut vérifier plus tard)

---

### 2.3 Récupérer l'abonnement actif

```
GET /subscription/my-subscription/
Authorization: Bearer <token>
```

**Réponse succès (200) :**
```json
{
  "success": true,
  "data": {
    "id": 42,
    "pack": {
      "id": 1,
      "name": "Pack Essentiel",
      "price": "2000.00",
      "image_corrections_limit": 20,
      "chat_questions_limit": 50,
      "duration": 30
    },
    "image_corrections_remaining": 20,
    "chat_questions_remaining": 50,
    "is_active": true,
    "created_at": "2026-02-27T10:00:00Z",
    "expires_at": "2026-03-29T10:00:00Z"
  }
}
```

**Réponse sans abonnement (404) :**
```json
{ "success": false, "message": "Aucun abonnement actif." }
```

---

### 2.4 Liste des packs disponibles

```
GET /subscription/create-packs/
Authorization: Bearer <token>
```

**Réponse (200) :**
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": 1,
      "name": "Pack Essentiel",
      "description": "Idéal pour débuter",
      "price": "2000.00",
      "image_corrections_limit": 20,
      "chat_questions_limit": 50,
      "duration": 30,
      "is_best_plan": false,
      "features": ["20 corrections d'images", "50 questions chatbot", "Support email"],
      "subscribers_count": 145
    }
  ]
}
```

---

## 3. Code Flutter — Implémentation

### 3.1 ApiService — Méthodes paiement

```dart
// lib/services/api_service.dart

/// Initie un paiement GeniusPay.
/// Retourne payment_url (checkout GeniusPay) + token_pay si succès.
static Future<Map<String, dynamic>> subscribeToPack(
  int packId,
  String phoneNumber,
) async {
  try {
    final accessToken = await _storage.read(key: 'access_token');
    if (accessToken == null) {
      return {'success': false, 'message': 'Utilisateur non connecté.', 'statusCode': 401};
    }

    final response = await http.post(
      Uri.parse('${Constants.baseUrl}subscription/subscribe/'),
      headers: {
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': 'Bearer $accessToken',
      },
      body: jsonEncode({
        'pack_id': packId,
        'phone_number': phoneNumber,
        'return_url': 'corrigemoi://payment-success',
        'error_url': 'corrigemoi://payment-error',
      }),
    );

    final data = jsonDecode(utf8.decode(response.bodyBytes));

    if ((response.statusCode == 200 || response.statusCode == 201) &&
        data['success'] == true) {
      return {
        'success': true,
        'payment_url': data['payment_url'], // URL checkout pay.genius.ci à ouvrir
        'token_pay': data['token_pay'],      // Référence MTX-XXXXXXXX pour le polling
        'pack': data['pack'],
        'amount': data['amount'],
        'statusCode': response.statusCode,
      };
    }
    return {
      'success': false,
      'message': data['message'] ?? 'Échec de l\'initiation du paiement.',
      'statusCode': response.statusCode,
    };
  } catch (e) {
    return {'success': false, 'message': 'Erreur de connexion: $e', 'statusCode': 0};
  }
}

/// Vérifie le statut du paiement côté backend (qui interroge GeniusPay).
/// À appeler toutes les 3 secondes depuis le WebView screen.
static Future<Map<String, dynamic>> getPaymentStatus(String tokenPay) async {
  try {
    final accessToken = await _storage.read(key: 'access_token');
    if (accessToken == null) return {'success': false, 'payment_status': 'error'};

    final response = await http.get(
      Uri.parse('${Constants.baseUrl}subscription/payment/status/$tokenPay/'),
      headers: {
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': 'Bearer $accessToken',
      },
    );

    final data = jsonDecode(utf8.decode(response.bodyBytes));

    if (response.statusCode == 200 && data['success'] == true) {
      return {
        'success': true,
        'payment_status': data['payment_status'], // 'pending'|'paid'|'failed'|'cancelled'
        'pack': data['pack'],
        'amount': data['amount'],
      };
    }
    return {
      'success': false,
      'payment_status': 'error',
      'message': data['message'],
    };
  } catch (e) {
    return {'success': false, 'payment_status': 'error'};
  }
}
```

---

### 3.2 Écran de détail pack — Déclenchement du paiement

```dart
// lib/screens/pack_detail_screen.dart

Future<void> _handleSubscribe() async {
  if (_isLoading) return;

  // 1. Demander le numéro Mobile Money
  final phoneController = TextEditingController();
  final phone = await showDialog<String>(
    context: context,
    builder: (ctx) => Dialog(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Numéro Mobile Money',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              'Wave, Orange Money, MTN ou Moov',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: phoneController,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                hintText: 'Ex: 0701234567',
                prefixIcon: Icon(Icons.phone),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Annuler'),
                  ),
                ),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () =>
                        Navigator.pop(ctx, phoneController.text.trim()),
                    child: const Text('Payer'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );

  if (phone == null || phone.isEmpty) return;

  // 2. Appel API pour initier le paiement
  setState(() => _isLoading = true);
  final result = await ApiService.subscribeToPack(widget.pack.id, phone);
  setState(() => _isLoading = false);

  if (!mounted) return;

  if (result['success'] == true) {
    // 3. Naviguer vers le WebView de paiement (page checkout GeniusPay)
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => PaymentWebViewScreen(
          paymentUrl: result['payment_url'] as String,   // pay.genius.ci/checkout/...
          tokenPay: result['token_pay'] as String,        // MTX-XXXXXXXXXX
          packName: result['pack'] as String? ?? widget.pack.name,
          amount: result['amount'] as String? ??
              widget.pack.price.toStringAsFixed(0),
        ),
      ),
    );
  } else {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(result['message'] as String? ??
            'Erreur lors de l\'initiation du paiement.'),
        backgroundColor: Colors.red,
      ),
    );
  }
}
```

---

### 3.3 Écran WebView avec polling

```dart
// lib/screens/payment_webview_screen.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../providers/subscription_provider.dart';
import '../providers/stats_provider.dart';
import '../services/api_service.dart';

class PaymentWebViewScreen extends StatefulWidget {
  final String paymentUrl; // URL checkout pay.genius.ci à ouvrir
  final String tokenPay;   // Référence MTX-XXXXXXXX pour le polling
  final String packName;
  final String amount;

  const PaymentWebViewScreen({
    Key? key,
    required this.paymentUrl,
    required this.tokenPay,
    required this.packName,
    required this.amount,
  }) : super(key: key);

  @override
  State<PaymentWebViewScreen> createState() => _PaymentWebViewScreenState();
}

class _PaymentWebViewScreenState extends State<PaymentWebViewScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  bool _showSuccess = false;
  Timer? _pollTimer;
  int _pollAttempts = 0;
  static const int _maxAttempts = 40; // 40 × 3s = 2 min

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(NavigationDelegate(
        onPageStarted: (_) => setState(() => _isLoading = true),
        onPageFinished: (_) {
          setState(() => _isLoading = false);
          _startPolling(); // Démarre le polling dès que la page checkout est chargée
        },
      ))
      ..loadRequest(Uri.parse(widget.paymentUrl));
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _checkStatus(),
    );
  }

  Future<void> _checkStatus() async {
    if (++_pollAttempts > _maxAttempts) {
      _pollTimer?.cancel();
      return; // Timeout silencieux après 2 min
    }

    final result = await ApiService.getPaymentStatus(widget.tokenPay);
    if (!mounted) return;

    final status = result['payment_status'] as String?;

    if (status == 'paid') {
      _pollTimer?.cancel();
      await _onSuccess();
    } else if (status == 'cancelled' || status == 'failed') {
      _pollTimer?.cancel();
      _onFailure(status!);
    }
    // 'pending' → continuer le polling
  }

  Future<void> _onSuccess() async {
    // Rafraîchir l'abonnement et les stats — DANS CET ORDRE
    await context.read<SubscriptionProvider>().loadSubscription();
    context.read<StatsProvider>().loadStats();

    if (!mounted) return;
    setState(() => _showSuccess = true);
  }

  void _onFailure(String status) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Paiement échoué'),
        content: Text(
          status == 'cancelled'
              ? 'Paiement annulé. Vous pouvez réessayer.'
              : 'Une erreur est survenue. Veuillez réessayer.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context); // Ferme dialog
              Navigator.pop(context); // Retourne à PackDetail
            },
            child: const Text('Retour'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context); // Ferme dialog
              setState(() => _pollAttempts = 0);
              _controller.reload();
              _startPolling();
            },
            child: const Text('Réessayer'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_showSuccess) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.check_circle, color: Colors.green, size: 80),
                const SizedBox(height: 20),
                const Text(
                  'Paiement confirmé !',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  '${widget.packName} activé · ${widget.amount} CFA',
                  style: const TextStyle(color: Colors.grey),
                ),
                const SizedBox(height: 40),
                ElevatedButton(
                  onPressed: () {
                    Navigator.pop(context); // Retour à PackDetail
                    Navigator.pop(context); // Retour à PacksScreen
                  },
                  child: const Text('Commencer maintenant'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.packName} · ${widget.amount} CFA'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: _confirmCancel,
        ),
        actions: [
          // Indicateur vert = polling actif (backend surveille GeniusPay)
          if (_pollTimer != null && _pollTimer!.isActive)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.green,
                ),
              ),
            ),
        ],
      ),
      body: Stack(
        children: [
          WebViewWidget(controller: _controller),
          if (_isLoading) const Center(child: CircularProgressIndicator()),
        ],
      ),
    );
  }

  Future<void> _confirmCancel() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Quitter le paiement ?'),
        content: const Text('Le paiement sera annulé.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Rester'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Quitter', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirm == true && mounted) {
      _pollTimer?.cancel();
      Navigator.pop(context);
    }
  }
}
```

---

### 3.4 Dépendances pubspec.yaml requises

```yaml
dependencies:
  http: ^1.1.0
  flutter_secure_storage: ^9.2.4
  provider: ^6.0.5
  webview_flutter: ^4.10.0
```

---

## 4. Providers à rafraîchir après paiement

Après confirmation (`payment_status == 'paid'`), appeler **dans cet ordre** :

```dart
// 1. Rafraîchit l'objet Subscription (quota, dates, pack actif)
await context.read<SubscriptionProvider>().loadSubscription();

// 2. Rafraîchit les stats (corrections restantes, questions restantes)
context.read<StatsProvider>().loadStats();
```

---

## 5. Gestion des erreurs courantes

| Erreur backend                          | Cause                                       | Action Flutter                        |
|-----------------------------------------|---------------------------------------------|---------------------------------------|
| `"pack_id et phone_number sont requis"` | Champ manquant dans le body                 | Valider le formulaire avant envoi     |
| `"Vous êtes déjà abonné à ce pack."`   | Même pack actif non expiré                 | Désactiver le bouton si pack actuel   |
| `"Service de paiement non configuré."`  | Clés GeniusPay manquantes côté backend      | Contacter le backend dev              |
| `"Erreur de connexion au service..."`   | Backend ne peut pas joindre `pay.genius.ci` | Afficher retry                        |
| `payment_status == 'failed'`            | Échec Mobile Money (solde, réseau…)         | Afficher dialogue réessayer           |
| `payment_status == 'cancelled'`         | Annulé sur la page checkout GeniusPay       | Afficher dialogue retour / réessayer  |

---

## 6. Test en développement

### Tester l'initiation du paiement

```bash
curl -X POST http://172.20.10.2:8000/api/subscription/subscribe/ \
  -H "Authorization: Bearer <votre_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "pack_id": 1,
    "phone_number": "0701234567",
    "return_url": "https://example.com/success",
    "error_url": "https://example.com/error"
  }'
```

**Réponse attendue :**
```json
{
  "success": true,
  "payment_url": "https://pay.genius.ci/checkout/MTX-XXXXXXXXXX",
  "token_pay": "MTX-XXXXXXXXXX",
  "pack": "Pack Essentiel",
  "amount": "2000"
}
```

### Vérifier le statut (polling manuel)

```bash
curl -X GET http://172.20.10.2:8000/api/subscription/payment/status/MTX-XXXXXXXXXX/ \
  -H "Authorization: Bearer <votre_jwt_token>"
```

### Vérifier l'abonnement après paiement

```bash
curl -X GET http://172.20.10.2:8000/api/subscription/my-subscription/ \
  -H "Authorization: Bearer <votre_jwt_token>"
```

---

## 7. Points importants

- **Page de checkout hébergée** : GeniusPay affiche une page (`pay.genius.ci/checkout/...`) où l'utilisateur choisit Wave, Orange, MTN ou Moov. Aucune gestion de moyen de paiement côté app.
- **Pas de webhook en dev** : le backend interroge directement `pay.genius.ci` à chaque appel polling. Pas besoin de configurer de webhook pendant le développement.
- **Idempotence** : si le polling appelle le backend plusieurs fois avec le même `token_pay`, l'abonnement ne sera activé qu'une seule fois.
- **Cumul de quotas** : si l'utilisateur a un abonnement actif et en souscrit un nouveau, les quotas restants sont cumulés (ex: 5 corrections restantes + 20 du nouveau pack = 25 total).
- **Sécurité** : le endpoint `/payment/status/{token}/` vérifie que la transaction appartient bien à l'utilisateur connecté.
- **Timeout** : après 2 minutes de polling sans réponse, s'arrêter silencieusement. En production, l'abonnement sera activé via webhook dès que GeniusPay confirme.

---

## 8. Environnements

| Variable          | Développement                          | Production                                          |
|-------------------|----------------------------------------|-----------------------------------------------------|
| `baseUrl`         | `http://172.20.10.2:8000/api/`         | `https://correction-app-backend.onrender.com/api/`  |
| GeniusPay API     | `https://pay.genius.ci/api/v1/merchant`| `https://pay.genius.ci/api/v1/merchant`             |
| GeniusPay keys    | Sandbox (`pk_sandbox_...`)             | Live (`pk_live_...`)                                |
| Webhook           | Non requis                             | Configurer dans dashboard GeniusPay                 |
| `return_url`      | `corrigemoi://payment-success`         | Deep link ou URL HTTPS de la production             |

---

*Document généré pour le projet "Corrige Moi" — Intégration GeniusPay v1.1* merci
