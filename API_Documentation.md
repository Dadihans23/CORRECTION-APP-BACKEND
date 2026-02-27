# API Marchand GeniusPay

## Introduction

L'API Marchand GeniusPay permet aux développeurs d'intégrer facilement les paiements mobiles (Wave, Orange Money, MTN Money) et par carte dans leurs applications. Cette documentation couvre tous les endpoints disponibles, les méthodes d'authentification et les bonnes pratiques d'intégration.

### Base URL

```
Production : https://pay.genius.ci/api/v1/merchant
Sandbox    : https://pay.genius.ci/api/v1/merchant
```

> **Note**: Les environnements sandbox et production utilisent la même URL. La distinction se fait via les clés API utilisées.

---

## Authentification

### Clés API

Chaque marchand dispose de deux paires de clés :

| Type | Préfixe | Usage |
|------|---------|-------|
| **Sandbox** | `pk_sandbox_` / `sk_sandbox_` | Tests et développement |
| **Production** | `pk_live_` / `sk_live_` | Transactions réelles |

### Headers requis

```http
X-API-Key: pk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx
X-API-Secret: sk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
Accept: application/json
```

### Exemple avec cURL

```bash
curl -X POST https://pay.genius.ci/api/v1/merchant/payments \
  -H "X-API-Key: pk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "X-API-Secret: sk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"amount": 5000, "customer": {"phone": "+221771234567"}}'
```

### Exemple avec PHP

```php
$client = new \GuzzleHttp\Client();

$response = $client->post('https://pay.genius.ci/api/v1/merchant/payments', [
    'headers' => [
        'X-API-Key' => 'pk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx',
        'X-API-Secret' => 'sk_sandbox_xxxxxxxxxxxxxxxxxxxxxxxx',
        'Content-Type' => 'application/json',
    ],
    'json' => [
        'amount' => 5000,
        'customer' => [
            'phone' => '+221771234567',
        ],
    ],
]);

$data = json_decode($response->getBody(), true);
```

### Codes d'erreur d'authentification

| Code HTTP | Message | Description |
|-----------|---------|-------------|
| 401 | `MISSING_API_KEY` | Header X-API-Key manquant |
| 401 | `INVALID_API_KEY` | Clé API invalide ou inactive |
| 401 | `MISSING_API_SECRET` | Header X-API-Secret manquant |
| 401 | `INVALID_API_SECRET` | Secret API invalide |
| 403 | `MERCHANT_INACTIVE` | Compte marchand désactivé |
| 403 | `API_DISABLED` | API non activée pour ce compte |

---

## Paiements

### Initier un paiement

Crée une nouvelle transaction de paiement et retourne une URL de paiement.

```http
POST /payments
```

#### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `amount` | number | ✅ | Montant en XOF (minimum 100) |
| `currency` | string | ❌ | Devise (défaut: `XOF`) |
| `payment_method` | string | ❌ | Méthode: `wave`, `paystack`, `orange_money`, `mtn_money` |
| `description` | string | ❌ | Description du paiement (max 500 caractères) |
| `customer.name` | string | ❌ | Nom du client |
| `customer.email` | string | ❌ | Email du client |
| `customer.phone` | string | ❌ | Téléphone du client |
| `success_url` | string | ❌ | URL de redirection après succès |
| `error_url` | string | ❌ | URL de redirection après échec |
| `metadata` | object | ❌ | Données personnalisées (stockées avec la transaction) |

#### Requête

```json
{
  "amount": 15000,
  "currency": "XOF",
  "payment_method": "wave",
  "description": "Commande #12345",
  "customer": {
    "name": "Amadou Diallo",
    "email": "amadou@example.com",
    "phone": "+221771234567"
  },
  "success_url": "https://monsite.com/paiement/succes",
  "error_url": "https://monsite.com/paiement/echec",
  "metadata": {
    "order_id": "12345",
    "product_name": "Abonnement Premium"
  }
}
```

#### Réponse (201 Created)

```json
{
  "success": true,
  "data": {
    "id": 456,
    "reference": "MTX-A1B2C3D4E5",
    "product_reference": "TXN-XXXXXXXXXXXX",
    "amount": 15000,
    "currency": "XOF",
    "fees": 450,
    "net_amount": 14550,
    "status": "pending",
    "payment_url": "https://wave.com/checkout/abc123xyz",
    "gateway": "wave",
    "gateway_reference": "wave_ref_123",
    "environment": "sandbox",
    "expires_at": "2025-12-09T18:00:00.000000Z"
  }
}
```

#### Flux de paiement

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Votre App  │────▶│  GeniusPay  │────▶│   Gateway   │────▶│   Client    │
│             │     │     API     │     │ (Wave/etc)  │     │  (Mobile)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │
      │  POST /payments   │                   │                   │
      │──────────────────▶│                   │                   │
      │                   │  Init payment     │                   │
      │                   │──────────────────▶│                   │
      │                   │◀──────────────────│                   │
      │  payment_url      │                   │                   │
      │◀──────────────────│                   │                   │
      │                   │                   │                   │
      │        Redirect client to payment_url │                   │
      │─────────────────────────────────────────────────────────▶│
      │                   │                   │   Paiement mobile │
      │                   │                   │◀──────────────────│
      │                   │  Webhook callback │                   │
      │                   │◀──────────────────│                   │
      │  Webhook (votre   │                   │                   │
      │  endpoint)        │                   │                   │
      │◀──────────────────│                   │                   │
```

---

### Lister les paiements

Récupère la liste des paiements du marchand.

```http
GET /payments
```

#### Paramètres de query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `status` | string | Filtrer par statut: `pending`, `completed`, `failed`, `cancelled` |
| `payment_method` | string | Filtrer par méthode de paiement |
| `from` | date | Date de début (YYYY-MM-DD) |
| `to` | date | Date de fin (YYYY-MM-DD) |
| `search` | string | Recherche par référence, email ou téléphone |
| `per_page` | integer | Nombre de résultats par page (max 100, défaut 20) |

#### Réponse

```json
{
  "success": true,
  "data": [
    {
      "id": 456,
      "reference": "MTX-A1B2C3D4E5",
      "amount": 15000,
      "currency": "XOF",
      "fees": 450,
      "net_amount": 14550,
      "status": "completed",
      "payment_method": "wave",
      "customer": {
        "name": "Amadou Diallo",
        "email": "amadou@example.com",
        "phone": "+221771234567"
      },
      "environment": "sandbox",
      "created_at": "2025-12-08T10:30:00.000000Z",
      "completed_at": "2025-12-08T10:32:15.000000Z"
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 20,
    "total": 145,
    "last_page": 8
  }
}
```

---

### Récupérer un paiement

Récupère les détails d'un paiement spécifique.

```http
GET /payments/{reference}
```

#### Réponse

```json
{
  "success": true,
  "data": {
    "id": 456,
    "reference": "MTX-A1B2C3D4E5",
    "amount": 15000,
    "currency": "XOF",
    "fees": 450,
    "net_amount": 14550,
    "status": "completed",
    "payment_method": "wave",
    "payment_provider": "wave",
    "environment": "sandbox",
    "customer": {
      "name": "Amadou Diallo",
      "email": "amadou@example.com",
      "phone": "+221771234567"
    },
    "metadata": {
      "order_id": "12345"
    },
    "created_at": "2025-12-08T10:30:00.000000Z",
    "completed_at": "2025-12-08T10:32:15.000000Z"
  }
}
```

---

## Compte

### Informations du compte

```http
GET /account
```

#### Réponse

```json
{
  "success": true,
  "data": {
    "id": "uuid-merchant-123",
    "name": "Ma Boutique",
    "email": "contact@maboutique.com",
    "type": "business",
    "status": "active",
    "environment": "sandbox",
    "api_mode": "sandbox",
    "balance": {
      "available": 1250000,
      "pending": 75000,
      "currency": "XOF"
    },
    "limits": {
      "monthly": 50000000,
      "used": 12500000,
      "available": 37500000
    },
    "commission_rate": 3.0,
    "is_early_adopter": true
  }
}
```

### Solde du compte

```http
GET /account/balance
```

#### Réponse

```json
{
  "success": true,
  "data": {
    "available": 1250000,
    "pending": 75000,
    "total": 1325000,
    "currency": "XOF"
  }
}
```

---

## Webhooks

Les webhooks permettent de recevoir des notifications en temps réel sur les événements de vos paiements.

### Événements disponibles

| Événement | Description |
|-----------|-------------|
| `payment.initiated` | Paiement initié |
| `payment.success` | Paiement réussi |
| `payment.failed` | Paiement échoué |
| `payment.cancelled` | Paiement annulé |
| `payment.refunded` | Paiement remboursé |
| `cashout.initiated` | Retrait initié |
| `cashout.completed` | Retrait effectué |
| `cashout.failed` | Retrait échoué |

### Lister les webhooks

```http
GET /webhooks
```

### Créer un webhook

```http
POST /webhooks
```

#### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `url` | string | ✅ | URL de réception (HTTPS requis en production) |
| `name` | string | ❌ | Nom du webhook |
| `events` | array | ❌ | Liste des événements (tous par défaut) |

#### Requête

```json
{
  "name": "Mon webhook principal",
  "url": "https://monsite.com/webhooks/geniuspay",
  "events": ["payment.success", "payment.failed"]
}
```

#### Réponse

```json
{
  "success": true,
  "data": {
    "id": 123,
    "uuid": "wh_abc123",
    "name": "Mon webhook principal",
    "url": "https://monsite.com/webhooks/geniuspay",
    "secret": "whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "environment": "sandbox",
    "events": ["payment.success", "payment.failed"],
    "status": "active",
    "created_at": "2025-12-08T10:00:00.000000Z"
  },
  "message": "Webhook created successfully. Save the secret, it will not be shown again."
}
```

> ⚠️ **Important**: Le `secret` n'est affiché qu'une seule fois à la création. Conservez-le précieusement.

### Payload des webhooks

Chaque webhook reçoit un payload JSON avec la structure suivante :

```json
{
  "event": "payment.success",
  "timestamp": "2025-12-08T10:32:15.000000Z",
  "data": {
    "transaction": {
      "id": 456,
      "reference": "MTX-A1B2C3D4E5",
      "amount": 15000,
      "currency": "XOF",
      "fees": 450,
      "net_amount": 14550,
      "status": "completed",
      "payment_method": "wave",
      "customer": {
        "name": "Amadou Diallo",
        "email": "amadou@example.com",
        "phone": "+221771234567"
      },
      "metadata": {
        "order_id": "12345"
      },
      "created_at": "2025-12-08T10:30:00.000000Z",
      "completed_at": "2025-12-08T10:32:15.000000Z"
    },
    "merchant": {
      "id": "uuid-merchant-123",
      "name": "Ma Boutique"
    },
    "environment": "sandbox"
  }
}
```

### Headers des webhooks

| Header | Description |
|--------|-------------|
| `X-GeniusPay-Signature` | Signature HMAC-SHA256 du payload |
| `X-GeniusPay-Timestamp` | Timestamp Unix de l'envoi |
| `X-GeniusPay-Event` | Type d'événement |
| `X-GeniusPay-Delivery-ID` | ID unique de la livraison |

### Vérification de la signature

```php
function verifyWebhookSignature($payload, $signature, $secret) {
    $expectedSignature = hash_hmac('sha256', $payload, $secret);
    return hash_equals($expectedSignature, $signature);
}

// Dans votre controller
$payload = file_get_contents('php://input');
$signature = $_SERVER['HTTP_X_GENIUSPAY_SIGNATURE'];
$secret = 'whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx';

if (!verifyWebhookSignature($payload, $signature, $secret)) {
    http_response_code(401);
    exit('Invalid signature');
}

$event = json_decode($payload, true);
// Traiter l'événement...
```

### Tester un webhook

```http
POST /webhooks/{id}/test
```

Envoie un événement de test à votre endpoint.

### Modifier un webhook

```http
PUT /webhooks/{id}
```

### Supprimer un webhook

```http
DELETE /webhooks/{id}
```

---

## Statuts des paiements

| Statut | Description |
|--------|-------------|
| `pending` | En attente de paiement |
| `processing` | Paiement en cours de traitement |
| `completed` | Paiement réussi |
| `failed` | Paiement échoué |
| `cancelled` | Paiement annulé |
| `refunded` | Paiement remboursé |
| `expired` | Paiement expiré (après 24h) |

---

## Méthodes de paiement

| Code | Nom | Pays | Devise |
|------|-----|------|--------|
| `wave` | Wave | SN, CI, ML, BF | XOF |
| `orange_money` | Orange Money | SN, CI, ML, BF | XOF |
| `mtn_money` | MTN Mobile Money | CI, BF | XOF |
| `moov_money` | Moov Money | CI, BF | XOF |
| `paystack` | Carte bancaire | NG, GH, ZA, KE | NGN, GHS, ZAR, KES |

---

## Gestion des erreurs

### Format des erreurs

```json
{
  "success": false,
  "error": {
    "code": "PAYMENT_INIT_FAILED",
    "message": "Limite mensuelle atteinte"
  }
}
```

### Codes d'erreur courants

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 422 | Données invalides |
| `PAYMENT_INIT_FAILED` | 400 | Échec d'initialisation du paiement |
| `TRANSACTION_NOT_FOUND` | 404 | Transaction introuvable |
| `WEBHOOK_NOT_FOUND` | 404 | Webhook introuvable |
| `MONTHLY_LIMIT_EXCEEDED` | 400 | Limite mensuelle dépassée |
| `MERCHANT_INACTIVE` | 403 | Compte marchand inactif |
| `GATEWAY_ERROR` | 502 | Erreur du prestataire de paiement |

---

## Limites de taux (Rate Limiting)

| Endpoint | Limite |
|----------|--------|
| `POST /payments` | 100 requêtes/minute |
| `GET /payments` | 300 requêtes/minute |
| Autres | 600 requêtes/minute |

Les headers de réponse incluent :

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1702051200
```

---

## Exemples d'intégration

### PHP (Laravel)

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

class GeniusPayService
{
    protected string $baseUrl = 'https://pay.genius.ci/api/v1/merchant';
    protected string $apiKey;
    protected string $apiSecret;

    public function __construct()
    {
        $this->apiKey = config('services.geniuspay.api_key');
        $this->apiSecret = config('services.geniuspay.api_secret');
    }

    public function initiatePayment(array $data): array
    {
        $response = Http::withHeaders([
            'X-API-Key' => $this->apiKey,
            'X-API-Secret' => $this->apiSecret,
        ])->post("{$this->baseUrl}/payments", $data);

        return $response->json();
    }

    public function getPayment(string $reference): array
    {
        $response = Http::withHeaders([
            'X-API-Key' => $this->apiKey,
            'X-API-Secret' => $this->apiSecret,
        ])->get("{$this->baseUrl}/payments/{$reference}");

        return $response->json();
    }
}
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

class GeniusPayClient {
  constructor(apiKey, apiSecret) {
    this.client = axios.create({
      baseURL: 'https://pay.genius.ci/api/v1/merchant',
      headers: {
        'X-API-Key': apiKey,
        'X-API-Secret': apiSecret,
        'Content-Type': 'application/json',
      },
    });
  }

  async initiatePayment(data) {
    const response = await this.client.post('/payments', data);
    return response.data;
  }

  async getPayment(reference) {
    const response = await this.client.get(`/payments/${reference}`);
    return response.data;
  }

  async getBalance() {
    const response = await this.client.get('/account/balance');
    return response.data;
  }
}

// Utilisation
const geniuspay = new GeniusPayClient(
  'pk_sandbox_xxx',
  'sk_sandbox_xxx'
);

const payment = await geniuspay.initiatePayment({
  amount: 15000,
  payment_method: 'wave',
  customer: {
    phone: '+221771234567',
  },
});

console.log('Payment URL:', payment.data.payment_url);
```

### Python

```python
import requests
import hmac
import hashlib

class GeniusPayClient:
    def __init__(self, api_key, api_secret):
        self.base_url = 'https://pay.genius.ci/api/v1/merchant'
        self.headers = {
            'X-API-Key': api_key,
            'X-API-Secret': api_secret,
            'Content-Type': 'application/json',
        }

    def initiate_payment(self, amount, customer_phone, **kwargs):
        data = {
            'amount': amount,
            'customer': {'phone': customer_phone},
            **kwargs
        }
        response = requests.post(
            f'{self.base_url}/payments',
            json=data,
            headers=self.headers
        )
        return response.json()

    def get_payment(self, reference):
        response = requests.get(
            f'{self.base_url}/payments/{reference}',
            headers=self.headers
        )
        return response.json()

    @staticmethod
    def verify_webhook_signature(payload, signature, secret):
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# Utilisation
client = GeniusPayClient('pk_sandbox_xxx', 'sk_sandbox_xxx')

payment = client.initiate_payment(
    amount=15000,
    customer_phone='+221771234567',
    payment_method='wave',
    description='Commande #12345'
)

print(f"Payment URL: {payment['data']['payment_url']}")
```

---

## Bonnes pratiques

### 1. Toujours vérifier les signatures webhook

Ne traitez jamais un webhook sans vérifier sa signature.

### 2. Implémenter l'idempotence

Stockez la `reference` de chaque transaction et vérifiez qu'elle n'a pas déjà été traitée.

### 3. Gérer les échecs gracieusement

```php
try {
    $payment = $geniuspay->initiatePayment($data);
} catch (Exception $e) {
    // Logger l'erreur
    Log::error('Payment failed', ['error' => $e->getMessage()]);
    
    // Informer l'utilisateur
    return response()->json([
        'error' => 'Le paiement a échoué. Veuillez réessayer.'
    ], 500);
}
```

### 4. Utiliser les webhooks plutôt que le polling

Au lieu de vérifier régulièrement le statut d'un paiement, configurez un webhook pour être notifié automatiquement.

### 5. Tester en sandbox avant la production

Utilisez toujours les clés sandbox pour développer et tester votre intégration.

### 6. Stocker les métadonnées utiles

Utilisez le champ `metadata` pour stocker des informations de votre système (order_id, user_id, etc.).

---

## Support

- **Documentation**: https://docs.geniuspay.io
- **Email**: support@geniuspay.io
- **Dashboard**: https://pay.geniuspay.io/dashboard

---

## Changelog

### v1.0.0 (2025-12-08)
- Lancement initial de l'API Marchand
- Support Wave, Paystack, Orange Money, MTN Money
- Système de webhooks avec retry automatique
- Mode sandbox et production
