"""
SenderX Standard SMTP Email Adapter
Production-ready SMTP integration supporting:
- STARTTLS and SSL/TLS transport
- Plain, Login, and CRAM-MD5 authentication
- Single & multiple recipients
- CC, BCC, Reply-To
- Plain-text and HTML body
- Dynamic template rendering
- Attachments with size validation
- Custom headers
- Retry classification (Auth, Refused, Network/Timeout, ServerBusy)
- Response normalization
- Credential redaction
"""

from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid
import smtplib
import socket
from typing import Any, Dict, List, Optional
import uuid

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.email.email_utils import (
    parse_recipients,
    validate_attachments,
    render_template,
    redact_sensitive,
    normalize_provider_response,
    is_valid_email
)


class SMTPAdapter(BaseChannelAdapter):

    def __init__(
        self,
        smtp_host: str,
        from_email: str,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 15
    ):
        if not smtp_host or not str(smtp_host).strip():
            raise ValueError("SMTP smtp_host is required")
        if not from_email or not is_valid_email(from_email):
            raise ValueError(f"Invalid SMTP from_email: '{from_email}'")

        try:
            self.smtp_port = int(smtp_port)
        except (ValueError, TypeError):
            self.smtp_port = 587

        self.smtp_host = str(smtp_host).strip()
        self.from_email = from_email.strip()
        self.smtp_user = str(smtp_user).strip() if smtp_user else None
        self._smtp_password = str(smtp_password).strip() if smtp_password else None
        self.use_tls = bool(use_tls)
        self.use_ssl = bool(use_ssl)
        self.timeout = int(timeout) if timeout else 15

    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate SMTP message structure."""
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        data = message.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Email data must be an object")

        recipient = message.get("recipient")
        to_list = data.get("to") or data.get("recipients") or recipient
        recipients = parse_recipients(to_list)
        if not recipients:
            raise ValueError("At least one valid recipient email is required")

        subject = data.get("subject") or message.get("subject")
        if not subject:
            raise ValueError("Email subject is required")

        content = data.get("message") or data.get("content") or data.get("text")
        html_content = data.get("html") or data.get("html_content")
        if not content and not html_content:
            raise ValueError("Email plain-text content or html is required")

        if "cc" in data:
            parse_recipients(data["cc"])
        if "bcc" in data:
            parse_recipients(data["bcc"])
        if "reply_to" in data and data["reply_to"]:
            if not is_valid_email(data["reply_to"]):
                raise ValueError(f"Invalid reply_to address: '{data['reply_to']}'")

        if "attachments" in data and data["attachments"]:
            validate_attachments(data["attachments"])

        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and template-render the message into normalized email parameters."""
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
            "attachments": attachments,
            "headers": headers,
            "message_id": message.get("message_id")
        }

    def _build_mime_message(self, formatted: Dict[str, Any]) -> MIMEMultipart:
        """Construct full MIME email message."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = formatted["subject"]
        msg["From"] = formatted["from_email"]
        msg["To"] = ", ".join(formatted["recipients"])
        msg["Date"] = formatdate(localtime=True)

        # Message ID for threading and provider correlation
        msg_id_domain = self.from_email.split("@")[-1] if "@" in self.from_email else "senderx.io"
        msg["Message-ID"] = make_msgid(domain=msg_id_domain)

        if formatted["cc"]:
            msg["Cc"] = ", ".join(formatted["cc"])
        if formatted["reply_to"]:
            msg["Reply-To"] = formatted["reply_to"]

        # Custom headers
        if formatted["headers"]:
            for k, v in formatted["headers"].items():
                msg[k] = str(v)

        # Body container
        body_part = MIMEMultipart("alternative")
        if formatted["plain_content"]:
            body_part.attach(MIMEText(formatted["plain_content"], "plain", "utf-8"))
        if formatted["html_content"]:
            body_part.attach(MIMEText(formatted["html_content"], "html", "utf-8"))
        msg.attach(body_part)

        # Attachments
        for att in formatted["attachments"]:
            part = MIMEApplication(att["raw_bytes"])
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=att["filename"]
            )
            part.add_header("Content-Type", att["mime_type"])
            msg.attach(part)

        return msg

    def _create_connection(self):
        """Create and authenticate an SMTP connection."""
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)

        server.ehlo()

        if self.use_tls and not self.use_ssl:
            server.starttls()
            server.ehlo()

        if self.smtp_user and self._smtp_password:
            server.login(self.smtp_user, self._smtp_password)

        return server

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch email through the SMTP server."""
        self.validate(message)
        formatted = self.format_message(message)

        mime_msg = self._build_mime_message(formatted)
        all_recipients = formatted["recipients"] + formatted["cc"] + formatted["bcc"]
        message_id = mime_msg.get("Message-ID", f"smtp-{uuid.uuid4().hex[:12]}")

        server = None
        try:
            server = self._create_connection()
            server.send_message(mime_msg, from_addr=formatted["from_email"], to_addrs=all_recipients)
            server.quit()

            return normalize_provider_response(
                success=True,
                provider="smtp",
                channel="email",
                provider_message_id=message_id,
                status="SENT"
            )

        except smtplib.SMTPAuthenticationError as error:
            clean_details = redact_sensitive(str(error), [self._smtp_password])
            raise ProviderError(
                f"SMTP authentication failure [AUTH_ERROR]: {clean_details}",
                status_code=getattr(error, "smtp_code", 535),
                retryable=False,
                error_code="AUTH_ERROR"
            ) from None

        except (smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused) as error:
            clean_details = redact_sensitive(str(error), [self._smtp_password])
            raise ProviderError(
                f"SMTP recipient/sender refused [INVALID_RECIPIENT]: {clean_details}",
                status_code=getattr(error, "smtp_code", 550),
                retryable=False,
                error_code="INVALID_RECIPIENT"
            ) from None

        except smtplib.SMTPDataError as error:
            code = getattr(error, "smtp_code", 500)
            retryable = (400 <= code < 500)
            clean_details = redact_sensitive(str(error), [self._smtp_password])
            raise ProviderError(
                f"SMTP data rejected: {clean_details}",
                status_code=code,
                retryable=retryable,
                error_code="RATE_LIMIT" if code in (421, 451, 452) else ("TEMPORARY_ERROR" if retryable else "INVALID_PAYLOAD")
            ) from None

        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, ConnectionError) as error:
            clean_details = redact_sensitive(str(error), [self._smtp_password])
            raise ProviderError(
                f"SMTP network transport failure [NETWORK_ERROR]: {clean_details}",
                status_code=None,
                retryable=True,
                error_code="NETWORK_ERROR"
            ) from None

        except Exception as error:
            clean_details = redact_sensitive(str(error), [self._smtp_password])
            raise ProviderError(
                f"Unexpected SMTP failure [PROVIDER_ERROR]: {clean_details}",
                status_code=None,
                retryable=True,
                error_code="PROVIDER_ERROR"
            ) from None

        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Delivery status retrieval for SMTP messages."""
        return {
            "success": True,
            "provider": "smtp",
            "provider_message_id": provider_message_id,
            "status": "SENT",
            "message": "SMTP message handed off to remote MTA."
        }
