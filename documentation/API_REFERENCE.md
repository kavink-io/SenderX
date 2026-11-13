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
