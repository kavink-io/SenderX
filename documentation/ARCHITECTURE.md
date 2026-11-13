# SenderX Architecture & System Design

SenderX is an enterprise-grade, multi-tenant, multi-channel messaging platform engineered with Python Flask, MongoDB Atlas, Redis, RabbitMQ, and Celery.

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    Client["Client / Frontend Dashboard"] -->|HTTPS / REST API| FlaskAPI["SenderX Flask REST API"]
    
    subgraph Security_Layer["Security & Isolation"]
        JWT["JWT Authenticator"]
        RBAC["Role & Permission Guard"]
        TenantGuard["Tenant Context (organization_id)"]
    end
    
    FlaskAPI --> JWT
    JWT --> RBAC
    RBAC --> TenantGuard
    
    subgraph Data_Storage["Data Storage Layer"]
        MongoDB[("MongoDB Atlas Database")]
        Vault[("Encrypted Provider Configs")]
    end
    
    TenantGuard -->|Isolated Queries| MongoDB
    TenantGuard -->|Fernet Decryption| Vault
    
    subgraph Asynchronous_Queue["Asynchronous Queue Engine"]
        Broker["RabbitMQ Message Broker"]
        RedisCache[("Redis Cache & Result Backend")]
        CeleryWorker["Celery Background Workers"]
    end
    
    FlaskAPI -->|Task Dispatch| Broker
    Broker --> CeleryWorker
    CeleryWorker <--> RedisCache
    CeleryWorker <--> MongoDB
    
    subgraph Provider_Layer["Provider Adapter Layer"]
        SendGridAdapter["SendGrid API Adapter"]
        MockAdapter["Mock Scenario Adapter"]
        FutureAdapters["Twilio / WhatsApp / Telegram"]
    end
    
    CeleryWorker --> SendGridAdapter
    CeleryWorker --> MockAdapter
    CeleryWorker --> FutureAdapters
```

---

## 2. Message Lifecycle & State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED: Message Submitted
    CREATED --> VALIDATED: Dynamic JSON Analyzer
    VALIDATED --> QUEUED: Enqueued to Celery
    QUEUED --> PROCESSING: Worker Consumes Task
    PROCESSING --> SENT: Provider Delivery Accepted
    
    PROCESSING --> RETRYING: Retryable Error (1st & 2nd)
    RETRYING --> PROCESSING: Exponential Backoff (5s, 10s, 20s)
    
    PROCESSING --> FAILED: Non-Retryable Error (4xx)
    PROCESSING --> DEAD: Retries Exhausted (Attempt 3)
    
    DEAD --> PENDING_REVIEW: Saved to Dead Letter Queue (DLQ)
    PENDING_REVIEW --> RETRY_REQUESTED: Admin Requests Manual Retry
    RETRY_REQUESTED --> RETRY_QUEUED: Celery Dispatches Manual Task
    RETRY_QUEUED --> PROCESSING: Worker Consumes Manual Task
    
    SENT --> RESOLVED: DLQ Resolved (Manual Retry Success)
```

---

## 3. Dead Letter Queue & Manual Retry Flow

1. **Exhaustion**: When automated retries reach `MAX_RETRIES = 3`, the worker marks the message status as `DEAD` and invokes `DeadLetterRepository.save_from_message()`.
2. **Initial DLQ State**: An entry is created or updated in `dead_letters` with `dead_letter_status = "PENDING_REVIEW"` and `cycle_type = "AUTOMATIC"`.
3. **Manual Retry Trigger**: An authorized administrator triggers manual retry via `POST /api/v1/dead-letters/organization/<message_id>/retry`.
   - `mark_retry_requested()` atomically reserves the record, increments `manual_retry_count`, and pre-generates a unique `task_id`.
   - `MessageRepository.requeue_dead_message()` resets message `status = "QUEUED"` and `retry_count = 0`.
   - Celery publishes `senderx.process_message` using the exact pre-generated `task_id`.
   - `mark_retry_queued()` sets `dead_letter_status = "RETRY_QUEUED"` and `manual_retry_dispatch_state = "QUEUED"`.
4. **Resolution on Success**:
   - The worker marks message `SENT`.
   - Compares `self.request.id == dlq_record["manual_retry_task_id"]`.
   - Atomically updates DLQ to `RESOLVED` and `manual_retry_dispatch_state = "COMPLETED"`.
   - Preserves complete historical failure cycles.
5. **Re-exhaustion on Failure**:
   - If manual retry fails again, worker calls `save_from_message()`.
   - Adds a deterministic `MANUAL` failure cycle.
   - Moves DLQ back to `PENDING_REVIEW` with `manual_retry_dispatch_state = "COMPLETED"`.
   - Marks `manual_retry_history` entry as `FAILED`.
