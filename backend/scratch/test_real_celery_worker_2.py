import sys
sys.path.insert(0, "backend")
from dotenv import load_dotenv
load_dotenv("backend/.env")

import os
# Use local test MongoDB like pytest conftest does
os.environ["MONGO_URI"] = "mongodb://localhost:27017/?directConnection=true"
os.environ["MONGO_DB"] = "SenderX_test"

import subprocess, time, uuid, os
from app import create_app
from app.modules.messages.repository import MessageRepository
from app.queue.tasks import process_message

app = create_app()

sg_key = "SG.v29skd920skd920skd920.abcdefghijklmnopqrstuvwxyz12345"
jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
secret_pw = "SuperSecretAdminPass123!"

with app.app_context():
    org_id = str(uuid.uuid4())
    msg_fail = f"msg_wfail_{uuid.uuid4().hex[:6]}"
    msg_succ = f"msg_wsucc_{uuid.uuid4().hex[:6]}"
    
    # 1. Controlled failure message with secrets
    MessageRepository.save({
        "message_id": msg_fail,
        "organization_id": org_id,
        "channel": "email",
        "provider": "mock",
        "recipient": "fail-worker@senderx.test",
        "status": "QUEUED",
        "data": {
            "channel": "email",
            "recipient": "fail-worker@senderx.test",
            "subject": "Permanent Secret Leak Failure Test",
            "body": "Confidential original body content",
            "mock_scenario": "secret_leak_failure",
            "mock_error_message": f"SendGrid API failure: auth SG.{sg_key[3:]} failed with JWT {jwt_token} and password={secret_pw}"
        },
        "retry_count": 0,
        "created_at": "2026-11-20T12:00:00Z",
    })
    
    # 2. Valid subsequent message
    MessageRepository.save({
        "message_id": msg_succ,
        "organization_id": org_id,
        "channel": "email",
        "provider": "mock",
        "recipient": "succ-worker@senderx.test",
        "status": "QUEUED",
        "data": {
            "channel": "email",
            "recipient": "succ-worker@senderx.test",
            "subject": "Success After Failure Test",
            "body": "Success message body",
            "mock_scenario": "success",
        },
        "retry_count": 0,
        "created_at": "2026-11-20T12:00:00Z",
    })

# Start worker subprocess with MONGO_DB=SenderX_test
env = os.environ.copy()
env["MONGO_DB"] = "SenderX_test"
env["PYTHONUNBUFFERED"] = "1"
env["PYTHONPATH"] = "backend"

log_f = open("backend/scratch/worker.log", "w")
cmd = [sys.executable, "-m", "celery", "-A", "app.queue.celery_app.celery", "worker", "-n", f"test_worker_{uuid.uuid4().hex[:4]}@%h", "-Q", "test_isolation_queue", "--without-mingle", "--without-gossip", "--pool=solo", "--loglevel=INFO"]
worker = subprocess.Popen(cmd, cwd="backend", env=env, stdout=log_f, stderr=subprocess.STDOUT, text=True)

try:
    time.sleep(4) # Wait for worker startup
    print("Dispatching Task 1 (Controlled failure with secrets)...")
    r1 = process_message.apply_async(args=[msg_fail], queue="test_isolation_queue")
    print("Task 1 ID:", r1.id)
    
    # Poll for Task 1 completion
    for _ in range(10):
        time.sleep(1)
        with app.app_context():
            m1 = MessageRepository.find_by_id(msg_fail, org_id)
            if m1 and m1.get("status") in ("FAILED", "DEAD"):
                print("Task 1 finished with status:", m1.get("status"))
                break
                
    print("Dispatching Task 2 (Valid subsequent task)...")
    r2 = process_message.apply_async(args=[msg_succ], queue="test_isolation_queue")
    print("Task 2 ID:", r2.id)
    
    # Poll for Task 2 completion
    for _ in range(10):
        time.sleep(1)
        with app.app_context():
            m2 = MessageRepository.find_by_id(msg_succ, org_id)
            if m2 and m2.get("status") in ("SENT", "DELIVERED"):
                print("Task 2 finished with status:", m2.get("status"))
                break
                
    with app.app_context():
        m1 = MessageRepository.find_by_id(msg_fail, org_id)
        m2 = MessageRepository.find_by_id(msg_succ, org_id)
        print("Final M1 Status:", m1.get("status"))
        print("Final M2 Status:", m2.get("status"))
        
        # Verify secret redaction on m1 error
        err1 = m1.get("error") or m1.get("last_error") or ""
        print("M1 Stored Error:", err1)
        assert sg_key not in err1, "SendGrid key leaked!"
        assert jwt_token not in err1, "JWT leaked!"
        assert secret_pw not in err1, "Password leaked!"
        assert "[REDACTED_API_KEY]" in err1 or "[REDACTED" in err1
        assert "[REDACTED_JWT]" in err1
        print("Secrets REDACTED successfully in persisted error!")
        
        # Verify immutability of original payload
        assert m1["data"]["body"] == "Confidential original body content"
        assert m1["data"]["subject"] == "Permanent Secret Leak Failure Test"
        print("Original message payload remained 100% immutable!")
        
        # Verify m2 was delivered
        assert m2["status"] == "SENT"
        print("Worker survived and successfully delivered second message!")
finally:
    worker.terminate()
    try:
        worker.wait(timeout=3)
    except Exception:
        worker.kill()
    log_f.close()
