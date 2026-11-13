"""
SenderX SendGrid Email Adapter
Production-ready SendGrid integration supporting:
- Single & multiple recipients
- CC, BCC, Reply-To
- Plain-text and HTML body
- Dynamic template rendering
- Attachments with size validation
- Custom headers
- Retry classification (429 Rate Limit, 5xx Outages, 401/403 Auth, 4xx Validation)
- Response normalization
- Credential redaction
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Cc,
    Bcc,
    ReplyTo,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
    CustomArg,
    Header
)

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.email.email_utils import (
    parse_recipients,
    validate_attachments,
    render_template,
    redact_sensitive,
    normalize_provider_response,
    is_valid_email
)


class SendGridAdapter(BaseChannelAdapter):

    def __init__(self, api_key: str, from_email: str):
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("SendGrid api_key is required")
        if not from_email or not isinstance(from_email, str) or not is_valid_email(from_email):
            raise ValueError(f"Invalid SendGrid from_email: '{from_email}'")

        self._api_key = api_key.strip()
        self.from_email = from_email.strip()
        self.client = SendGridAPIClient(api_key=self._api_key)

    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate email message payload structure."""
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        data = message.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Email data must be an object")

        # 1. Resolve recipients
        recipient = message.get("recipient")
        to_list = data.get("to") or data.get("recipients") or recipient
        recipients = parse_recipients(to_list)
        if not recipients:
            raise ValueError("At least one valid recipient email is required")

        # 2. Subject validation (required unless template_id is used)
        subject = data.get("subject") or message.get("subject")
        template_id = data.get("template_id")
        if not subject and not template_id:
            raise ValueError("Email subject is required")

        # 3. Content validation (content, html, or template_id required)
        content = data.get("message") or data.get("content") or data.get("text")
        html_content = data.get("html") or data.get("html_content")
        if not content and not html_content and not template_id:
            raise ValueError("Email content or template_id is required")

        # 4. Optional CC/BCC/Reply-To validation
        if "cc" in data:
            parse_recipients(data["cc"])
        if "bcc" in data:
            parse_recipients(data["bcc"])
        if "reply_to" in data and data["reply_to"]:
            if not is_valid_email(data["reply_to"]):
                raise ValueError(f"Invalid reply_to address: '{data['reply_to']}'")

        # 5. Attachments validation
        if "attachments" in data and data["attachments"]:
            validate_attachments(data["attachments"])

        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and template-render the message into a normalized email format."""
        data = message.get("data", {})
        template_vars = data.get("template_vars") or data.get("template_data") or data.get("variables")

        recipient = message.get("recipient")
        to_list = data.get("to") or data.get("recipients") or recipient
        recipients = parse_recipients(to_list)

        raw_subject = data.get("subject") or message.get("subject") or ""
        subject = render_template(raw_subject, template_vars)

        raw_text = data.get("message") or data.get("content") or data.get("text") or ""
        plain_content = render_template(raw_text, template_vars) if raw_text else None

        raw_html = data.get("html") or data.get("html_content") or ""
        html_content = render_template(raw_html, template_vars) if raw_html else None

        cc_list = parse_recipients(data.get("cc")) if data.get("cc") else []
        bcc_list = parse_recipients(data.get("bcc")) if data.get("bcc") else []
        reply_to = data.get("reply_to")

        attachments = validate_attachments(data.get("attachments", []))
        headers = data.get("headers", {})

        return {
            "from_email": self.from_email,
            "recipients": recipients,
            "cc": cc_list,
            "bcc": bcc_list,
            "reply_to": reply_to,
            "subject": subject,
            "plain_content": plain_content,
            "html_content": html_content,
            "template_id": data.get("template_id"),
            "dynamic_template_data": template_vars,
            "attachments": attachments,
            "headers": headers,
            "idempotency_key": message.get("message_id")
        }

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via SendGrid API client."""
        self.validate(message)
        formatted = self.format_message(message)

        # Build SendGrid Mail object
        mail = Mail()
        mail.from_email = Email(formatted["from_email"])
        mail.subject = formatted["subject"]

        # Add To recipients
        for to_addr in formatted["recipients"]:
            mail.add_to(To(to_addr))

        # Add CC / BCC
        for cc_addr in formatted["cc"]:
            mail.add_cc(Cc(cc_addr))
        for bcc_addr in formatted["bcc"]:
            mail.add_bcc(Bcc(bcc_addr))

        # Add Reply-To
        if formatted["reply_to"]:
            mail.reply_to = ReplyTo(formatted["reply_to"])

        # Body Content
        if formatted["html_content"]:
            mail.html_content = formatted["html_content"]
        if formatted["plain_content"]:
            mail.plain_text_content = formatted["plain_content"]

        # Dynamic Template
        if formatted["template_id"]:
            mail.template_id = formatted["template_id"]
            if formatted["dynamic_template_data"]:
                mail.dynamic_template_data = formatted["dynamic_template_data"]

        # Custom Headers
        if formatted["headers"] and isinstance(formatted["headers"], dict):
            for hk, hv in formatted["headers"].items():
                mail.add_header(Header(str(hk), str(hv)))

        # Idempotency / Tracking Custom Arg
        if formatted.get("idempotency_key"):
            mail.add_custom_arg(CustomArg("senderx_message_id", formatted["idempotency_key"]))

        # Attachments
        for att in formatted["attachments"]:
            sg_att = Attachment(
                FileContent(att["base64_content"]),
                FileName(att["filename"]),
                FileType(att["mime_type"]),
                Disposition("attachment")
            )
            mail.add_attachment(sg_att)

        # Dispatch via SendGrid Client
        try:
            response = self.client.send(mail)

            if response.status_code not in (200, 201, 202):
                status_code = response.status_code
                retryable = (status_code == 429 or status_code >= 500)
                error_code = "RATE_LIMIT" if status_code == 429 else "PROVIDER_ERROR"
                raise ProviderError(
                    f"SendGrid rejected message: HTTP {status_code}",
                    status_code=status_code,
                    retryable=retryable,
                    error_code=error_code
                )

            # Extract provider message ID
            provider_msg_id = None
            if hasattr(response, "headers") and response.headers:
                provider_msg_id = response.headers.get("X-Message-Id") or response.headers.get("x-message-id")
            if not provider_msg_id:
                provider_msg_id = f"sg-{message.get('message_id', 'unknown')}"

            return normalize_provider_response(
                success=True,
                provider="sendgrid",
                channel="email",
                provider_message_id=provider_msg_id,
                status="ACCEPTED"  # Provider accepted for queueing/delivery
            )

        except ProviderError:
            raise

        except Exception as error:
            status_code = getattr(error, "status_code", None)
            error_body = getattr(error, "body", None)
            retry_after = None

            if hasattr(error, "headers") and error.headers:
                retry_after = error.headers.get("Retry-After") or error.headers.get("retry-after")

            if isinstance(error_body, bytes):
                error_body = error_body.decode("utf-8", errors="replace")

            raw_details = str(error_body or str(error))
            details = redact_sensitive(raw_details, [self._api_key])[:2048]

            # Error Classification
            if status_code in (401, 403):
                retryable = False
                error_code = "AUTH_ERROR"
            elif status_code in (400, 422):
                retryable = False
                error_code = "INVALID_PAYLOAD"
            elif status_code == 429:
                retryable = True
                error_code = "RATE_LIMIT"
            elif status_code is not None and status_code >= 500:
                retryable = True
                error_code = "PROVIDER_OUTAGE"
            else:
                # Network or connection error
                retryable = True
                error_code = "NETWORK_ERROR"

            raise ProviderError(
                f"SendGrid API error [{error_code}] | HTTP: {status_code} | Details: {details}",
                status_code=status_code,
                retryable=retryable,
                error_code=error_code,
                retry_after=retry_after
            ) from None

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Delivery status retrieval for SendGrid messages."""
        return {
            "success": True,
            "provider": "sendgrid",
            "provider_message_id": provider_message_id,
            "status": "ACCEPTED",
            "message": "SendGrid message accepted by MTA. Webhook updates delivery confirmation."
        }
