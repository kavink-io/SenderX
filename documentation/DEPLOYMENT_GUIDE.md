# SenderX Deployment & Operations Guide

## 1. Prerequisites
- Python 3.11+
- MongoDB 7.0+ (Atlas or local replica set)
- Redis 7.0+
- RabbitMQ 3.12+
- Docker & Docker Compose (for containerized deployments)

---

## 2. Environment Configuration
For Docker Compose, create a `.env` file in the repository root. For direct
Windows development, create `backend/.env` from `backend/.env.example`.

```env
APP_NAME=SenderX
APP_ENV=production
DEBUG=False
SECRET_KEY=<generate-a-unique-random-secret>
CREDENTIAL_ENCRYPTION_KEY=<generate-a-unique-fernet-key>
OTP_HMAC_SECRET=<generate-a-separate-random-secret-of-at-least-32-characters>
AUTH_OTP_EMAIL_PROVIDER=sendgrid

# Database
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.ghm7ofm.mongodb.net/?compressors=zlib
MONGO_DB=SenderX_db

# Message Broker & Cache
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672//

# Live SendGrid Provider (verified sender required)
SENDGRID_API_KEY=SG.your_verified_api_key_here
SENDGRID_FROM_EMAIL=verified_sender@domain.com
```

For production, set these values in the deployment secret manager or an untracked
`.env` file; do not commit real credentials. Generate secrets with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use distinct random values for `SECRET_KEY` and `OTP_HMAC_SECRET`; the latter
must be at least 32 characters and must be identical in the API and Celery
worker. Configure exactly one platform email provider through the SUPER_ADMIN
provider configuration or deployment environment. If multiple providers are
configured, set `AUTH_OTP_EMAIL_PROVIDER` explicitly. Production rejects mock
providers and does not fall back to them. Email delivery requires a live
provider account, a verified sender, and a running Celery worker; Redis and
RabbitMQ must also be reachable. Keep the OTP secret unchanged across the API
and worker and during rolling deployments; queued OTP messages cannot be
decrypted if the key changes before delivery.

---

## 3. Running Locally (PowerShell / Windows)

### Step 1: Start Redis and RabbitMQ
Ensure local Redis and RabbitMQ service daemons are running on default ports `6379` and `5672`.

### Step 2: Initialize Platform Super Administrator
```powershell
& backend\venv\Scripts\python.exe backend\create_admin.py
```

### Step 3: Run the Celery Background Worker
```powershell
$env:PYTHONPATH="backend"
& backend\venv\Scripts\celery.exe -A run.celery worker --loglevel=info -P solo
```
*(On Windows development, `-P solo` ensures clean worker thread execution).*

### Step 4: Run the Production WSGI Web Server
```powershell
$env:PYTHONPATH="backend"
& backend\venv\Scripts\python.exe backend\run.py
```
Or with Gunicorn on Linux/production:
```bash
gunicorn --config backend/gunicorn_config.py run:app
```

---

## 4. Running with Docker Compose

Run from the project root (`SenderX`):

```bash
docker compose up --build -d
```
*(Or if inside `backend/`, navigate up first: `cd .. ; docker compose up --build -d`)*


Check health:
```bash
curl http://localhost:5000/api/v1/health/detailed
```

---

## 5. Automated Test Suite Execution

Run all 15 unit, integration, and manual retry test suites:
```powershell
$env:PYTHONPATH="backend"
& backend\venv\Scripts\python.exe -m pytest backend\tests -v
```
