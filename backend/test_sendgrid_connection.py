
import os
from sendgrid import SendGridAPIClient

api_key = os.getenv("SENDGRID_API_KEY")

if not api_key:
    raise ValueError("SENDGRID_API_KEY is not configured")

try:
    client = SendGridAPIClient(api_key=api_key)

    # Check API authentication without sending an email
    response = client.client.api_keys.get()

    print("HTTP Status:", response.status_code)

    if response.status_code == 200:
        print("SUCCESS: SendGrid API connected!")
    else:
        print("SendGrid returned an unexpected status.")

except Exception as error:
    print("SendGrid connection failed.")
    print("Error type:", type(error).__name__)

    status = getattr(error, "status_code", None)
    if status:
        print("HTTP Status:", status)

    body = getattr(error, "body", None)
    if body:
        print("Response:", body)
