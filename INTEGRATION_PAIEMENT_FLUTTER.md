# Intégration Paiement MoneyFusion — Flutter

**Projet :** Corrige Moi
**Backend :** Django REST API
**Paiement :** MoneyFusion (Orange Money, MTN, Wave, Moov)

---

## Vue d'ensemble du flow

```
App Flutter                   Backend Django              MoneyFusion
    │                               │                          │
    ├── POST /subscribe/ ──────────►│                          │
    │   {pack_id, phone_number}     │                          │
    │                               ├── POST MoneyFusion ─────►│
    │                               │◄── {token, url} ─────────┤
    │◄── {payment_url, token_pay} ──┤                          │
    │                               │                          │
    ├── WebView(payment_url) ──────────────────────────────────►│
    │                               │                          │ (user paie)
    │                               │◄── webhook ──────────────┤
    │                               │    (abonnement activé)   │
    │                               │                          │
    ├── GET /payment/status/{token} ►│                          │
    │◄── {payment_status: "paid"} ──┤                          │
    │                               │                          │
    ├── (abonnement actif) ─────────►│                          │
```

**Résumé :**
1. L'app initie le paiement → reçoit une URL MoneyFusion
2. L'app ouvre cette URL dans un WebView
3. L'utilisateur paie sur la page MoneyFusion
4. Le backend reçoit la confirmation (webhook) → active l'abonnement automatiquement
5. L'app poll le statut jusqu'à `"paid"` → affiche la confirmation

---

## Authentification

Tous les endpoints (sauf le webhook) nécessitent un token JWT dans les headers :

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Le token est obtenu via `POST /api/auth/login/`.

---

## Endpoints

### Base URL
```
https://votre-domaine.com   (ou http://10.x.x.x:8000 en dev local)
```

---

### 1. Lister les packs disponibles

```
GET /api/subscription/create-packs/
```

**Headers :** `Authorization: Bearer <token>`
**Body :** aucun

**Réponse 200 :**
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": 1,
      "name": "Pack Starter",
      "slug": "pack-starter",
      "price": "2000.00",
      "description": "Idéal pour démarrer",
      "features": ["10 corrections", "5 questions chat"],
      "image_corrections_limit": 10,
      "chat_questions_limit": 5,
      "duration": 30,
      "is_best_plan": false,
      "subscribers_count": 42
    },
    {
      "id": 2,
      "name": "Pack Pro",
      "slug": "pack-pro",
      "price": "5000.00",
      "description": "Pour les étudiants sérieux",
      "features": ["50 corrections", "30 questions chat", "Priorité"],
      "image_corrections_limit": 50,
      "chat_questions_limit": 30,
      "duration": 30,
      "is_best_plan": true,
      "subscribers_count": 128
    }
  ]
}
```

**Champs utiles :**
| Champ | Type | Description |
|-------|------|-------------|
| `id` | int | À envoyer dans la requête de souscription |
| `price` | string | Prix en CFA |
| `duration` | int | Durée en jours (0 = illimité) |
| `is_best_plan` | bool | Afficher badge "Recommandé" |
| `image_corrections_limit` | int | Quota corrections (0 = illimité) |
| `chat_questions_limit` | int | Quota chat (0 = illimité) |

---

### 2. Initier un paiement (souscrire à un pack)

```
POST /api/subscription/subscribe/
```

**Headers :** `Authorization: Bearer <token>`

**Body :**
```json
{
  "pack_id": 2,
  "phone_number": "0701234567",
  "return_url": "corrigemoi://payment-callback"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `pack_id` | int | ✅ | ID du pack choisi |
| `phone_number` | string | ✅ | Numéro mobile money de l'utilisateur |
| `return_url` | string | ❌ | URL/deep link où MoneyFusion redirige après paiement |

**Réponse 200 (succès) :**
```json
{
  "success": true,
  "message": "Paiement initié. Redirigez l'utilisateur vers payment_url.",
  "payment_url": "https://www.pay.moneyfusion.net/pay/6596aded36bd58823b084564",
  "token_pay": "5d58823b084564",
  "pack": "Pack Pro",
  "amount": "5000.00"
}
```

**⚠️ À faire immédiatement :** Stocker `token_pay` localement (SharedPreferences ou state), puis ouvrir `payment_url` dans un WebView.

**Réponses d'erreur :**
```json
// 400 - Déjà abonné au même pack
{"success": false, "message": "Vous êtes déjà abonné à ce pack."}

// 400 - Champs manquants
{"success": false, "message": "pack_id et phone_number sont requis."}

// 503 - Service de paiement non disponible
{"success": false, "message": "Service de paiement non configuré."}

// 503 - Erreur réseau vers MoneyFusion
{"success": false, "message": "Erreur de connexion au service de paiement."}
```

---

### 3. Vérifier le statut du paiement

```
GET /api/subscription/payment/status/{token_pay}/
```

**Headers :** `Authorization: Bearer <token>`

**Réponse 200 :**
```json
{
  "success": true,
  "payment_status": "paid",
  "pack": "Pack Pro",
  "amount": "5000.00",
  "created_at": "2025-05-09T12:50:45.412Z"
}
```

**Valeurs de `payment_status` :**
| Statut | Description | Action Flutter |
|--------|-------------|----------------|
| `pending` | En attente de paiement | Continuer à poller |
| `paid` | Paiement confirmé ✅ | Afficher succès, rafraîchir abonnement |
| `cancelled` | Annulé ou échoué | Afficher erreur |
| `failed` | Erreur technique | Afficher erreur, proposer retry |

**Réponse 404 :**
```json
{"success": false, "message": "Transaction non trouvée."}
```

---

### 4. Récupérer l'abonnement actif

```
GET /api/subscription/my-subscription/
```

À appeler après confirmation du paiement (`payment_status == "paid"`).

**Réponse 200 :**
```json
{
  "success": true,
  "data": {
    "id": 5,
    "pack": {
      "id": 2,
      "name": "Pack Pro",
      "price": "5000.00",
      "image_corrections_limit": 50,
      "chat_questions_limit": 30,
      "duration": 30
    },
    "remaining_images": 50,
    "remaining_questions": 30,
    "image_limit": 50,
    "question_limit": 30,
    "is_active": true,
    "expires_at": "2025-06-09T12:50:45.412Z",
    "expired": false
  }
}
```

**Réponse 404 :**
```json
{"success": false, "message": "Aucun abonnement actif."}
```

---

## Implémentation Flutter

### Dépendances recommandées (`pubspec.yaml`)
```yaml
dependencies:
  http: ^1.2.0
  webview_flutter: ^4.7.0
  shared_preferences: ^2.2.3
```

---

### Service de paiement

```dart
// lib/services/payment_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;

class PaymentService {
  final String baseUrl;
  final String token; // JWT de l'utilisateur connecté

  PaymentService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $token',
  };

  /// Initie un paiement MoneyFusion pour un pack.
  /// Retourne {payment_url, token_pay} en cas de succès.
  Future<Map<String, dynamic>> initiatePayment({
    required int packId,
    required String phoneNumber,
    String returnUrl = '',
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/subscription/subscribe/'),
      headers: _headers,
      body: jsonEncode({
        'pack_id': packId,
        'phone_number': phoneNumber,
        'return_url': returnUrl,
      }),
    );

    final data = jsonDecode(response.body);

    if (response.statusCode == 200 && data['success'] == true) {
      return {
        'payment_url': data['payment_url'],
        'token_pay': data['token_pay'],
        'pack': data['pack'],
        'amount': data['amount'],
      };
    }

    throw PaymentException(
      data['message'] ?? 'Erreur lors de l\'initialisation du paiement',
      statusCode: response.statusCode,
    );
  }

  /// Vérifie le statut d'un paiement par son token.
  Future<String> checkPaymentStatus(String tokenPay) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/subscription/payment/status/$tokenPay/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['payment_status']; // "pending", "paid", "cancelled", "failed"
    }

    if (response.statusCode == 404) {
      throw PaymentException('Transaction introuvable');
    }

    throw PaymentException('Erreur de vérification du statut');
  }

  /// Récupère l'abonnement actif de l'utilisateur.
  Future<Map<String, dynamic>?> getActiveSubscription() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/subscription/my-subscription/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['data'];
    }
    return null; // 404 = pas d'abonnement actif
  }
}

class PaymentException implements Exception {
  final String message;
  final int? statusCode;

  PaymentException(this.message, {this.statusCode});

  @override
  String toString() => message;
}
```

---

### Écran de saisie du numéro + sélection du pack

```dart
// lib/screens/subscribe_screen.dart

import 'package:flutter/material.dart';
import 'payment_webview_screen.dart';
import '../services/payment_service.dart';

class SubscribeScreen extends StatefulWidget {
  final Map<String, dynamic> pack; // données du pack sélectionné

  const SubscribeScreen({super.key, required this.pack});

  @override
  State<SubscribeScreen> createState() => _SubscribeScreenState();
}

class _SubscribeScreenState extends State<SubscribeScreen> {
  final _phoneController = TextEditingController();
  bool _isLoading = false;
  String? _error;

  Future<void> _onPay() async {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) {
      setState(() => _error = 'Entrez votre numéro mobile money');
      return;
    }

    setState(() { _isLoading = true; _error = null; });

    try {
      final paymentService = PaymentService(
        baseUrl: 'https://votre-domaine.com',
        token: 'TOKEN_JWT_UTILISATEUR', // récupéré depuis votre auth state
      );

      final result = await paymentService.initiatePayment(
        packId: widget.pack['id'],
        phoneNumber: phone,
        returnUrl: 'corrigemoi://payment-callback',
      );

      if (!mounted) return;

      // Naviguer vers le WebView avec l'URL de paiement
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => PaymentWebViewScreen(
            paymentUrl: result['payment_url'],
            tokenPay: result['token_pay'],
            packName: result['pack'],
            amount: result['amount'],
          ),
        ),
      );
    } on PaymentException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'Erreur réseau. Vérifiez votre connexion.');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Paiement')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Résumé du pack
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.pack['name'],
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${widget.pack['price']} CFA',
                      style: TextStyle(
                        fontSize: 24,
                        color: Theme.of(context).primaryColor,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Saisie numéro
            TextField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(
                labelText: 'Numéro Mobile Money',
                hintText: 'Ex: 0701234567',
                prefixIcon: const Icon(Icons.phone),
                border: const OutlineInputBorder(),
                errorText: _error,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Entrez le numéro associé à votre compte Orange Money, MTN, Wave ou Moov.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 24),

            // Bouton payer
            ElevatedButton(
              onPressed: _isLoading ? null : _onPay,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: _isLoading
                ? const CircularProgressIndicator(color: Colors.white)
                : Text(
                    'Payer ${widget.pack['price']} CFA',
                    style: const TextStyle(fontSize: 16),
                  ),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

### WebView de paiement + polling du statut

```dart
// lib/screens/payment_webview_screen.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../services/payment_service.dart';

class PaymentWebViewScreen extends StatefulWidget {
  final String paymentUrl;
  final String tokenPay;
  final String packName;
  final String amount;

  const PaymentWebViewScreen({
    super.key,
    required this.paymentUrl,
    required this.tokenPay,
    required this.packName,
    required this.amount,
  });

  @override
  State<PaymentWebViewScreen> createState() => _PaymentWebViewScreenState();
}

class _PaymentWebViewScreenState extends State<PaymentWebViewScreen> {
  late final WebViewController _webViewController;
  Timer? _pollingTimer;
  String _statusMessage = 'En attente du paiement...';
  bool _paymentDone = false;

  @override
  void initState() {
    super.initState();
    _initWebView();
    _startPolling();
  }

  void _initWebView() {
    _webViewController = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(NavigationDelegate(
        onNavigationRequest: (request) {
          // Intercepter le deep link de retour (return_url)
          if (request.url.startsWith('corrigemoi://')) {
            _checkStatusNow();
            return NavigationDecision.prevent;
          }
          return NavigationDecision.navigate;
        },
      ))
      ..loadRequest(Uri.parse(widget.paymentUrl));
  }

  void _startPolling() {
    // Vérifier le statut toutes les 3 secondes
    _pollingTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (!_paymentDone) _checkStatusNow();
    });
  }

  Future<void> _checkStatusNow() async {
    try {
      final paymentService = PaymentService(
        baseUrl: 'https://votre-domaine.com',
        token: 'TOKEN_JWT_UTILISATEUR',
      );

      final statusStr = await paymentService.checkPaymentStatus(widget.tokenPay);

      if (!mounted) return;

      switch (statusStr) {
        case 'paid':
          _stopPolling();
          _onPaymentSuccess();
          break;
        case 'cancelled':
        case 'failed':
          _stopPolling();
          _onPaymentFailed(statusStr);
          break;
        case 'pending':
          // Continuer à attendre
          break;
      }
    } catch (e) {
      // Erreur réseau temporaire : ignorer et réessayer au prochain tick
    }
  }

  void _stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
    setState(() => _paymentDone = true);
  }

  void _onPaymentSuccess() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        icon: const Icon(Icons.check_circle, color: Colors.green, size: 56),
        title: const Text('Paiement réussi !'),
        content: Text(
          'Votre abonnement "${widget.packName}" est maintenant actif.\n\n'
          'Montant débité : ${widget.amount} CFA',
        ),
        actions: [
          ElevatedButton(
            onPressed: () {
              // Retourner à l'écran principal et rafraîchir
              Navigator.of(context).popUntil((route) => route.isFirst);
              // TODO: déclencher un refresh de l'état abonnement
            },
            child: const Text('Commencer'),
          ),
        ],
      ),
    );
  }

  void _onPaymentFailed(String status) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        icon: const Icon(Icons.error_outline, color: Colors.red, size: 56),
        title: const Text('Paiement échoué'),
        content: Text(
          status == 'cancelled'
            ? 'Le paiement a été annulé.'
            : 'Une erreur est survenue lors du paiement. Réessayez.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Fermer'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pop(context); // Retour à la sélection du pack
            },
            child: const Text('Réessayer'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Paiement MoneyFusion'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () {
            _stopPolling();
            Navigator.pop(context);
          },
        ),
      ),
      body: Stack(
        children: [
          WebViewWidget(controller: _webViewController),
          if (_paymentDone)
            const Center(child: CircularProgressIndicator()),
        ],
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        color: Colors.grey[100],
        child: Text(
          _statusMessage,
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, color: Colors.grey[600]),
        ),
      ),
    );
  }
}
```

---

## Cas particuliers à gérer

### Upgrade / Renouvellement
Le backend gère automatiquement les cas suivants :
- **Upgrade** : l'utilisateur change de pack → les quotas restants de l'ancien pack sont cumulés
- **Renouvellement** : l'abonnement a expiré → idem, quotas cumulés
- **Erreur "déjà abonné"** : si l'utilisateur tente de souscrire au même pack encore actif → afficher un message approprié

### Paiement en cours (app fermée puis rouverte)
Si l'utilisateur ferme l'app pendant le paiement, le `token_pay` doit être persisté (SharedPreferences). À l'ouverture de l'app, vérifier si un `token_pay` en cours existe et son statut.

```dart
// Sauvegarder avant d'ouvrir le WebView
final prefs = await SharedPreferences.getInstance();
await prefs.setString('pending_token_pay', tokenPay);

// À l'ouverture de l'app
final pendingToken = prefs.getString('pending_token_pay');
if (pendingToken != null) {
  final status = await paymentService.checkPaymentStatus(pendingToken);
  if (status == 'paid') {
    // Afficher confirmation et nettoyer
    await prefs.remove('pending_token_pay');
    // Rafraîchir abonnement
  }
}
```

---

## Test en développement

Pour tester sans paiement réel, le backend peut recevoir un webhook simulé :

```bash
# Simuler un paiement réussi (remplacer TOKEN_PAY par le token reçu)
curl -X POST http://localhost:8000/api/subscription/payment/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payin.session.completed",
    "tokenPay": "TOKEN_PAY_ICI",
    "moyen": "orange",
    "Montant": 5000,
    "numeroSend": "0701234567",
    "nomclient": "Test User"
  }'
```

---

## Résumé des endpoints

| Méthode | URL | Auth | Description |
|---------|-----|------|-------------|
| `GET` | `/api/subscription/create-packs/` | JWT | Liste des packs |
| `POST` | `/api/subscription/subscribe/` | JWT | Initie le paiement |
| `GET` | `/api/subscription/payment/status/{token}/` | JWT | Statut du paiement |
| `GET` | `/api/subscription/my-subscription/` | JWT | Abonnement actif |
| `GET` | `/api/subscription/dashboard/` | JWT | Dashboard complet |
| `GET` | `/api/subscription/transactions/` | JWT | Historique transactions |
| `POST` | `/api/subscription/payment/webhook/` | ❌ Aucune | Webhook MoneyFusion (serveur uniquement) |

---

*Documentation générée pour l'équipe Flutter — Backend Corrige Moi*
