# SenderX API Reference

All endpoints are prefixed with `/api/v1`. Authentication uses standard JWT Bearer tokens in the `Authorization: Bearer <token>` header.

---

## 1. Authentication (`/api/v1/auth`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/auth/login` | None | None | Authenticates Platform Admin or Organization User using email and password. |
| `POST` | `/auth/refresh` | Refresh JWT | None | Generates a new access token using a valid refresh token. |
| `GET` | `/auth/me` | JWT | None | Returns profile of the authenticated user or platform admin. |

---

## 2. Organization Management (`/api/v1/organizations`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/organizations/` | Admin JWT | `SUPER_ADMIN` | Creates an organization, its `ORG_ADMIN` role, and root administrator. |
| `GET` | `/organizations/` | Admin JWT | `SUPER_ADMIN` | Lists all organizations with pagination. |
| `GET` | `/organizations/<id>` | Admin JWT | `SUPER_ADMIN` | Retrieves organization details by ID. |
| `PATCH` | `/organizations/<id>/status` | Admin JWT | `SUPER_ADMIN` | Activates or deactivates an organization. |
| `GET` | `/organizations/current` | Org JWT | `organization:users:manage` | Returns current organization metadata for the authenticated user. |

---

## 3. Users & Role-Based Access Control (`/api/v1/users`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/users/` | Org JWT | `organization:users:manage` | Creates an organization member. Password must be >= 12 chars. |
| `GET` | `/users/` | Org JWT | `organization:users:manage` | Lists all users in the authenticated organization. |
| `GET` | `/users/<id>` | Org JWT | `organization:users:manage` | Retrieves user details by ID. |
| `PATCH` | `/users/<id>` | Org JWT | `organization:users:manage` | Updates user attributes (name, active status, role assignments). |
| `DELETE` | `/users/<id>` | Org JWT | `organization:users:manage` | Deactivates an organization user. |
| `POST` | `/users/roles` | Org JWT | `organization:roles:manage` | Creates a custom role scoped to the organization. Rejects wildcards. |
| `GET` | `/users/roles` | Org JWT | `organization:roles:manage` | Lists all organization roles (system & custom). |
| `GET` | `/users/permissions` | Org JWT | `organization:roles:manage` | Lists assignable organization permissions. |

---

## 4. Messages (`/api/v1/messages`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/messages/` | Org JWT | `organization:messages:create` | Validates and stores a new message with dynamic arbitrary JSON payload. |
| `GET` | `/messages/` | Org JWT | `organization:messages:read` | Lists organization messages with status, channel, provider, and date filters. |
| `GET` | `/messages/<id>` | Org JWT | `organization:messages:read` | Retrieves full message envelope and status history. |
| `PATCH` | `/messages/<id>/status` | Org JWT | `organization:messages:manage` | Transitions message status (e.g. `CREATED` -> `QUEUED`). |

For WhatsApp Cloud API POSTs, a connect timeout is retried because dispatch has not begun. A read timeout, connection reset, or other transport error after dispatch may mean Meta accepted the message; SenderX marks the message failed with `DELIVERY_OUTCOME_UNKNOWN` and does not retry automatically. `POST /messages/<id>/retry` returns `409` for this marker until the provider outcome is reconciled. Do not clear the marker or requeue blindly. Retryable Meta throttling honors `Retry-After` (bounded by the retry manager's 60-second ceiling); DLQ behavior for exhausted, explicitly retryable failures is unchanged.

### WhatsApp product and catalog messages

WhatsApp messages are created through `POST /api/v1/messages/` with `channel: "whatsapp"`, a selected `integration_id` (or `whatsapp_integration_id`), a recipient, and a `data` object. Configure a numeric `catalog_id` on that organization-owned integration with `PATCH /api/v1/whatsapp/integrations/<integration_id>` before sending product messages. The catalog ID in a `product` or `product_list` request must match the selected integration; dispatch uses the integration's value. The full-catalog `catalog_message` action does not contain a catalog ID, but still requires a catalog configured on the selected integration.

All three types are non-template interactive messages and remain subject to the existing WhatsApp 24-hour customer service window. A connected integration and configured catalog are required. SenderX does not locally verify that the catalog is linked to the WABA, that it contains inventory, that a retailer ID exists, or that Meta permissions permit delivery.

#### Single product

`interactive.action.catalog_id` must be numeric and match the selected integration. `product_retailer_id` must be a non-empty string. Body and footer are optional.

```json
{
  "channel": "whatsapp",
  "provider": "meta",
  "integration_id": "wai_example_integration",
  "recipient": "+15551234567",
  "data": {
    "type": "interactive",
    "interactive": {
      "type": "product",
      "body": {"text": "Take a look at this item"},
      "action": {
        "catalog_id": "123456789012345",
        "product_retailer_id": "SKU-EXAMPLE-1"
      }
    }
  }
}
```

#### Multiple products

Requires a text header, body, at least one non-empty section, and one or more retailer IDs in each section. Multiple sections require titles. There may be at most 30 products total. Footer is optional.

```json
{
  "channel": "whatsapp",
  "provider": "meta",
  "integration_id": "wai_example_integration",
  "recipient": "+15551234567",
  "data": {
    "type": "interactive",
    "interactive": {
      "type": "product_list",
      "header": {"type": "text", "text": "Shop our collection"},
      "body": {"text": "Choose an item to view"},
      "footer": {"text": "Prices shown in catalog"},
      "action": {
        "catalog_id": "123456789012345",
        "sections": [{
          "title": "Featured",
          "product_items": [
            {"product_retailer_id": "SKU-EXAMPLE-1"},
            {"product_retailer_id": "SKU-EXAMPLE-2"}
          ]
        }]
      }
    }
  }
}
```

#### Full catalog

Requires a body and `action.name: "catalog_message"`. The optional thumbnail retailer ID must be non-empty when supplied. This is distinct from `product` and `product_list`.

```json
{
  "channel": "whatsapp",
  "provider": "meta",
  "integration_id": "wai_example_integration",
  "recipient": "+15551234567",
  "data": {
    "type": "interactive",
    "interactive": {
      "type": "catalog_message",
      "body": {"text": "Browse our full catalog"},
      "action": {
        "name": "catalog_message",
        "parameters": {"thumbnail_product_retailer_id": "SKU-EXAMPLE-1"}
      }
    }
  }
}
```

Configure or clear the integration catalog using the organization-scoped integration endpoint:

```http
PATCH /api/v1/whatsapp/integrations/wai_example_integration
Authorization: Bearer <organization JWT>
Content-Type: application/json
```

```json
{"catalog_id": "123456789012345"}
```

Use `{"catalog_id": null}` to clear it. Invalid IDs, a missing configured catalog, a request catalog mismatch, an invalid product structure, a closed/missing customer service window, or Meta's rejection are surfaced as message validation/dispatch failures. Local validation cannot determine if a product is unavailable or a retailer ID is unmatched; those require provider verification.

### WhatsApp Flows management and data exchange

The routes below are organization scoped. Flow management requires an organization JWT with `organization:providers:manage`; Flow completion reads require `organization:messages:read`; deleting one requires `organization:messages:manage`. The integration ID in the path is resolved within the authenticated organization. Tokens and private keys are never returned by these routes.

| Method | Endpoint | Permission | Success / errors |
|---|---|---|---|
| `GET` | `/api/v1/whatsapp/integrations/<integration_id>/flows` | `organization:providers:manage` | `200` with `{success,data,count}`; `400` invalid/disconnected integration. |
| `POST` | `/api/v1/whatsapp/integrations/<integration_id>/flows` | `organization:providers:manage` | `201` with Flow; `400` invalid schema/configuration; `502` Meta failure. |
| `GET` | `/api/v1/whatsapp/integrations/<integration_id>/flows/<flow_id>` | `organization:providers:manage` | `200`; `404` outside tenant/not found. |
| `PATCH` | `/api/v1/whatsapp/integrations/<integration_id>/flows/<flow_id>` | `organization:providers:manage` | `200`; `400` invalid update; `404`; `502` Meta failure. |
| `POST` | `/api/v1/whatsapp/integrations/<integration_id>/flows/<flow_id>/publish` | `organization:providers:manage` | `200`; `404`; `502` Meta failure. |
| `POST` | `/api/v1/whatsapp/integrations/<integration_id>/flows/<flow_id>/deprecate` | `organization:providers:manage` | `200`; `404`; `502` Meta failure. |
| `POST` | `/api/v1/whatsapp/integrations/<integration_id>/flows/encryption-key` | `organization:providers:manage` | `200` with public-key fingerprint/status; `400`, `404`, or `502`. |
| `GET` | `/api/v1/whatsapp/integrations/<integration_id>/flow-completions/<provider_message_id>` | `organization:messages:read` | `200` with decrypted response for this tenant; `404` if integration/completion is not in scope. |
| `DELETE` | `/api/v1/whatsapp/integrations/<integration_id>/flow-completions/<provider_message_id>` | `organization:messages:manage` | `200` deleted; `404` outside tenant/not found. |

Flow create accepts JSON with `name` (1–60 characters), `categories` (non-empty list of Meta categories), optional `flow_json` (Flow JSON object with a `version` and non-empty `screens`), optional `publish`, and optional `clone_flow_id`. Endpoint-backed Flows additionally require `endpoint_enabled: true`, `endpoint_handlers` mapping action names or `SCREEN:action` to `{ "screen": "NEXT", "data": {} }`, and `flow_json.data_api_version` of `3.0` or `4.0`. They must be created as drafts, have an integration public key registered, and have an HTTPS `WHATSAPP_FLOW_ENDPOINT_BASE_URL` configured before publishing.

```json
{
  "name": "Appointment booking",
  "categories": ["APPOINTMENT_BOOKING"],
  "flow_json": {
    "version": "7.3",
    "data_api_version": "4.0",
    "screens": [{"id": "START", "title": "Book a visit", "layout": {"type": "SingleColumnLayout", "children": []}}]
  },
  "endpoint_enabled": true,
  "endpoint_handlers": {
    "INIT": {"screen": "START", "data": {}},
    "START:data_exchange": {"screen": "SUCCESS", "data": {"accepted": true}}
  }
}
```

Flow update accepts the same `name`, `categories`, `flow_json`, and endpoint handler fields as partial updates. Publishing and deprecating take no request body. Public-key registration takes no request body; it creates a new key pair, stores the private key encrypted, and registers the public key with Meta.

The endpoint handler model currently serves static configured responses; it is not a general-purpose business callback. Flow API failures are returned as sanitized generic `502` responses. Missing encryption configuration or invalid retention settings prevent safe persistence and cause webhook processing to request retry rather than store sensitive values in clear text.

Meta sends `POST /api/v1/whatsapp/flows/<integration_id>/<flow_id>/data` without a SenderX user JWT. Configure the matching Meta app secret. SenderX verifies `X-Hub-Signature-256` over the exact raw request bytes before decrypting. The encrypted JSON request contains Meta's documented `encrypted_flow_data`, `encrypted_aes_key`, and `initial_vector`; the decrypted request uses Meta's Flow fields (`version`, `action`, `screen`, `data`, `flow_token`, and optional `flow_token_signature`). Responses are AES-GCM encrypted and returned as Base64 `text/plain` with `Cache-Control: no-store`. Invalid signature returns `401`, unknown tenant Flow returns `404`, missing app secret returns `503`, oversized request returns `413`, and decryption failure returns `421`.

Flow completion values are stored in a separate Fernet-encrypted `whatsapp_flow_responses` collection. Inbound records use `payload_storage_version: 2`, keep the provider envelope shape with `response_json` replaced by `[ENCRYPTED_FLOW_RESPONSE]`, and omit the clear response from `content` and `structured_event`. `WHATSAPP_FLOW_RESPONSE_RETENTION_DAYS` controls TTL retention (default `90`, valid `1`–`3650` days); MongoDB TTL cleanup is asynchronous. The scoped GET route decrypts values only after resolving the connected integration under the authenticated organization. DELETE removes the encrypted response immediately. Existing legacy inbound records are not rewritten by this change.

The Flow data-exchange protocol does not provide a documented unique request ID. SenderX therefore deduplicates exact signed encrypted request bytes using a hash scoped to organization, integration, and Flow. Concurrent identical requests are not processed twice; a duplicate while processing receives `503`, and a completed duplicate gets the cached encrypted response. This does not deduplicate semantically identical requests re-encrypted with different IV/key material. Do not add side-effecting handlers without an explicit transactional or business-level idempotency key.

Flow endpoint deployment requires a public HTTPS URL with valid TLS, a per-WABA encryption key pair whose public key is registered with Meta, `CREDENTIAL_ENCRYPTION_KEY` (and configured previous keys during rotation), Meta app secret and webhook subscriptions, and the documented Flow API permissions/asset access. Tests use local cryptographic fixtures and mocked Meta responses; they do not verify live Meta delivery.

Re-registering a Flow encryption public key retains prior encrypted private-key entries on the integration. Endpoint decryption tries the current private key first, followed by retained previous keys for in-flight sessions. Integration responses omit both current and previous encrypted private keys. Keep the encryption keyring available until any data encrypted by it is retired; there is no automated previous Flow key retirement endpoint yet.

---

## 5. Dead Letter Queue (`/api/v1/dead-letters`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `GET` | `/dead-letters/organization` | Org JWT | `organization:dead_letters:read` | Lists DLQ records for the authenticated organization. |
| `GET` | `/dead-letters/organization/<id>` | Org JWT | `organization:dead_letters:read` | Retrieves DLQ details and historical failure cycles. |
| `POST` | `/dead-letters/organization/<id>/retry` | Org JWT | `organization:dead_letters:manage` | Triggers a manual retry with deduplication and task tracking. |
| `DELETE` | `/dead-letters/organization/<id>` | Org JWT | `organization:dead_letters:manage` | Deletes a DLQ record (requires `confirm: true`). |
| `GET` | `/dead-letters/` | Admin JWT | `SUPER_ADMIN`, `ADMIN` | Platform-wide DLQ inspection. |

---

## 6. Provider Configuration (`/api/v1/provider-config`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/provider-config/organization` | Org JWT | `organization:providers:manage` | Stores Fernet-encrypted provider credentials for the tenant. |
| `GET` | `/provider-config/organization` | Org JWT | `organization:providers:read` | Returns provider configuration status (never exposes secrets). |
| `POST` | `/provider-config/` | Admin JWT | None | Platform-level provider configuration fallback. |

---

## 7. Dynamic JSON Validation (`/api/v1/validation`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `POST` | `/validation/analyze` | None | None | Analyzes arbitrary JSON payload, extracts fields, and validates channel requirements. |

---

## 8. Analytics (`/api/v1/analytics`)

| Method | Endpoint | Auth | Permissions | Description |
|---|---|---|---|---|
| `GET` | `/analytics/platform` | Admin JWT | `SUPER_ADMIN` | Aggregates platform-wide message, provider, and channel statistics. |
| `GET` | `/analytics/organization` | Org JWT | `organization:analytics:read` | Strict tenant-isolated analytics and trends. |

---

## 9. System Health (`/api/v1/health`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health/` | None | Basic API heartbeat. |
| `GET` | `/health/detailed` | None | Checks Flask, MongoDB, Redis, RabbitMQ, and Celery workers. |
| `GET` | `/health/mongodb` | None | Direct MongoDB ping. |
| `GET` | `/health/redis` | None | Direct Redis ping. |
| `GET` | `/health/rabbitmq` | None | Direct RabbitMQ ping. |
| `GET` | `/health/celery` | None | Direct Celery worker ping. |
