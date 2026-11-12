
import os
from dotenv import load_dotenv

load_dotenv()

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Content,
    Personalization
)


api_key = os.getenv("SENDGRID_API_KEY")

if not api_key:
    raise ValueError("SENDGRID_API_KEY is not configured in .env file or environment")


# Replace with your actual verified sender address.
from_email = os.getenv("SENDGRID_FROM_EMAIL", "kavinvijay206@gmail.com")

# Replace with an actual recipient address you can access.
to_email = os.getenv("SENDGRID_TO_EMAIL", "kavinvijay1974@gmail.com")


# Create the email message explicitly.
message = Mail()

message.from_email = Email(from_email)

message.subject = "SenderX - SendGrid Integration Test"

message.add_content(
    Content(
        "text/html",
        """
        <h2>SenderX Email Integration</h2>
        <p>SendGrid API integration is being tested.</p>
        <p>This is a test email from SenderX.</p>
        """
    )
)

# Explicitly configure recipient.
personalization = Personalization()
personalization.add_to(Email(to_email))

message.add_personalization(personalization)


try:

    client = SendGridAPIClient(api_key)

    response = client.send(message)

    print("HTTP Status:", response.status_code)

    if response.status_code == 202:

        print("Email accepted by SendGrid!")

        print(
            "Provider Message ID:",
            response.headers.get("X-Message-Id")
        )

    else:

        print("Unexpected response:", response.body)

except Exception as error:

    print("Error type:", type(error).__name__)
    print("HTTP Status:", getattr(error, "status_code", "unavailable"))
    body = getattr(error, "body", None)
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    if body:
        safe_body = str(body).replace(api_key, "[REDACTED]")[:4096]
        print("Provider response:", safe_body)
