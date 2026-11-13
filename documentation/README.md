# SenderX: Enterprise Multi-Tenant Messaging Platform

SenderX is an asynchronous, multi-channel messaging platform built with Python Flask, MongoDB Atlas, Redis, RabbitMQ, and Celery. It enables organizations to create, validate, enqueue, and reliably dispatch messages across channels (Email, SMS, WhatsApp, Telegram) with automatic retry backoff, Dead Letter Queue (DLQ) tracking, manual retry capabilities, and full tenant data isolation.

---

## Key Capabilities

1. **Strict Multi-Tenancy & Data Isolation**:
   - Every organization-owned document includes `organization_id`.
   - All repository queries and aggregation pipelines strictly filter by `organization_id`.
   - Cross-tenant access is blocked at the authentication and database layer.

2. **Role-Based Access Control (RBAC)**:
   - Platform Level: `SUPER_ADMIN` with platform control and tenant management.
   - Organization Level: `ORG_ADMIN` automatically generated on organization creation. Custom roles with granular, non-wildcard permissions.

3. **Dynamic Arbitrary JSON Analyzer**:
   - Deep inspection and validation of nested JSON payloads, arbitrary structures, primitive and complex types.

4. **Resilient Asynchronous Queue & Exponential Backoff**:
   - 3-attempt exponential backoff retry strategy (`5s -> 10s -> 20s`).
   - Classification of retryable vs non-retryable permanent errors.

5. **Complete Dead Letter Queue & Manual Retry Lifecycle**:
   - Full failure-cycle tracking with preserved historical audits.
   - Idempotent manual retry dispatch with task ID correlation (`self.request.id == manual_retry_task_id`).
   - Automatic transition of DLQ to `RESOLVED` on successful delivery, and graceful re-entry into `PENDING_REVIEW` on repeated failure.

6. **Provider Layer**:
   - Integrated with live **SendGrid** API and resilient **Mock** test provider scenarios (`success`, `permanent_failure`, `temporary_failure`, `temporary_then_success`).
   - Tenant-scoped encrypted credential storage (Fernet cipher).

7. **Production Observability & Monitoring**:
   - Comprehensive health checks for Flask, MongoDB, Redis, RabbitMQ, and Celery workers.
   - Platform and organization-scoped analytics engines.

---

## Documentation Index
- [System Architecture & State Machines](ARCHITECTURE.md)
- [REST API Reference](API_REFERENCE.md)
- [Deployment & Operations Guide](DEPLOYMENT_GUIDE.md)
