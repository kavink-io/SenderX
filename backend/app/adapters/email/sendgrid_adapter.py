
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class ProviderError(Exception):
    """Provider error with retry classification."""

    def __init__(self, message, status_code=None, retryable=False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class SendGridAdapter:

    def __init__(self, api_key, from_email):
        self.client = SendGridAPIClient(api_key=api_key)
        self._api_key = api_key
        self.from_email = from_email

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not isinstance(recipient, str) or "@" not in recipient:
            raise ValueError("Invalid email recipient")

        if not isinstance(data, dict):
            raise ValueError("Email data must be an object")

        if not data.get("subject"):
            raise ValueError("Email subject is required")

        if not data.get("message") and not data.get("content"):
            raise ValueError("Email content is required")

        return True

    def format_message(self, message):
        data = message["data"]

        return {
            "from_email": self.from_email,
            "to_email": message["recipient"],
            "subject": data["subject"],
            "content": data.get("message") or data.get("content"),
            "html_content": data.get("html")
        }

    def send(self, message):
        self.validate(message)
        formatted = self.format_message(message)

        mail = Mail(
            from_email=formatted["from_email"],
            to_emails=formatted["to_email"],
            subject=formatted["subject"],
            plain_text_content=formatted["content"],
            html_content=formatted.get("html_content")
        )

        try:
            response = self.client.send(mail)

            if response.status_code != 202:
                status_code = response.status_code

                raise ProviderError(
                    f"SendGrid rejected the message: HTTP {status_code}",
                    status_code=status_code,
                    retryable=(status_code == 429 or status_code >= 500)
                )

            return {
                "success": True,
                "status": "SENT",
                "provider": "sendgrid",
                "provider_message_id": response.headers.get("X-Message-Id")
            }

        except ProviderError:
            raise

        except Exception as error:
            status_code = getattr(error, "status_code", None)
            error_body = getattr(error, "body", None)

            if isinstance(error_body, bytes):
                error_body = error_body.decode(
                    "utf-8",
                    errors="replace"
                )

            details = str(error_body or type(error).__name__)

            if self._api_key:
                details = details.replace(
                    self._api_key,
                    "[REDACTED]"
                )

            details = details[:4096]

            # HTTP 429 and 5xx are retryable.
            # Other HTTP 4xx errors are permanent.
            if status_code is not None:
                retryable = (
                    status_code == 429 or status_code >= 500
                )
            else:
                # No HTTP response usually indicates a transport failure.
                retryable = True

            raise ProviderError(
                f"SendGrid API error | HTTP: {status_code} | Details: {details}",
                status_code=status_code,
                retryable=retryable
            ) from None

    def get_status(self, provider_message_id):
        return {
            "success": False,
            "message": "Delivery webhook integration is pending"
        }
