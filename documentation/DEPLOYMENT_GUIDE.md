# SenderX Deployment & Operations Guide

## 1. Prerequisites
- Python 3.11+
- MongoDB 7.0+ (Atlas or local replica set)
- Redis 7.0+
- RabbitMQ 3.12+
- Docker & Docker Compose (for containerized deployments)

---

## 2. Environment Configuration
Create a `.env` file in `backend/` based on `backend/.env.example`:

```env
APP_NAME=SenderX
APP_ENV=production
DEBUG=False
SECRET_KEY=your_production_secret_key_here
CREDENTIAL_ENCRYPTION_KEY=B45B4HB-FzqHcEGTyh6W5FdKBKl2FRB9DHsyZVriewY=

# Database
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.ghm7ofm.mongodb.net/?compressors=zlib
MONGO_DB=SenderX_db

# Message Broker & Cache
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672//

# Live SendGrid Provider
SENDGRID_API_KEY=SG.your_verified_api_key_here
SENDGRID_FROM_EMAIL=verified_sender@domain.com
```

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
