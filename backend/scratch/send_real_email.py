import os
import sys
import time
from datetime import datetime, timezone
import dotenv

dotenv.load_dotenv('backend/.env')
sys.path.insert(0, 'backend')

from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.modules.templates.compiler import (
    compile_email_template,
    STARTER_TEMPLATE_HTML,
    STARTER_TEMPLATE_CSS,
    STARTER_TEMPLATE_VARIABLES
)
from app.modules.templates.security import TemplateSandboxRunner

api_key = os.getenv("SENDGRID_API_KEY")
from_email = os.getenv("SENDGRID_FROM_EMAIL", "kavinvijay206@gmail.com")
to_email = "kavinvijay1974@gmail.com"

print("=" * 60)
print("REAL EMAIL VERIFICATION (Task 5.6.1 Item 13)")
print("=" * 60)
print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
print(f"Provider: SendGrid")
print(f"From: {from_email}")
print(f"To: {to_email}")

# 1. Compile starter template with inline CSS and responsiveness
compiled = compile_email_template(STARTER_TEMPLATE_HTML, STARTER_TEMPLATE_CSS)
compiled_html = compiled["compiled_html"]
plain_text = compiled["plain_text"]

# 2. Render with sample variables
sample_context = {v["name"]: v["sample_value"] for v in STARTER_TEMPLATE_VARIABLES}
sample_context["brand_name"] = "SenderX Platform"
sample_context["subject"] = "SenderX Phase 5: Email Template Studio Live Verification"
sample_context["heading"] = "Email Template Studio Live Test"
sample_context["recipient_name"] = "Kavin K"
sample_context["cta_url"] = "https://senderx.io/verify"

rendered_html = TemplateSandboxRunner.render(compiled_html, sample_context)
rendered_subject = TemplateSandboxRunner.render(sample_context["subject"], sample_context)
rendered_text = TemplateSandboxRunner.render(plain_text, sample_context)

print(f"Rendered Subject: {rendered_subject}")

# 3. Initialize adapter
adapter = SendGridAdapter(api_key=api_key, from_email=from_email)

msg_id = f"msg-real-{int(time.time())}"
message_payload = {
    "message_id": msg_id,
    "recipient": to_email,
    "channel": "email",
    "provider": "sendgrid",
    "data": {
        "to": [to_email],
        "subject": rendered_subject,
        "html": rendered_html,
        "content": rendered_text
    }
}

t_queued = datetime.now(timezone.utc).isoformat()
print(f"[{t_queued}] Status: QUEUED (message_id: {msg_id})")

try:
    adapter.validate(message_payload)
    result = adapter.send(message_payload)
    t_sent = datetime.now(timezone.utc).isoformat()
    print(f"[{t_sent}] Status: SENT / ACCEPTED by SendGrid")
    print(f"Provider Response: {result}")
except Exception as e:
    t_failed = datetime.now(timezone.utc).isoformat()
    print(f"[{t_failed}] Status: FAILED - {e}")
