"""
SenderX Amazon SES Email Adapter
Production-ready Amazon SES integration supporting:
- Single & multiple recipients
- CC, BCC, Reply-To
- Plain-text and HTML body
- Dynamic template rendering
- Attachments via Raw MIME message
- Custom headers
- Retry classification (Throttling, ServiceUnavailable, AuthFailure, MessageRejected)
- Response normalization
- Credential redaction
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.email.email_utils import (
    parse_recipients,
    validate_attachments,
    validate_email_headers,
    validate_no_crlf,
    render_template,
    redact_sensitive,
    normalize_provider_response,
    is_valid_email
)


class AmazonSESAdapter(BaseChannelAdapter):

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        from_email: str,
        aws_region: str = "us-east-1",
        aws_session_token: Optional[str] = None
    ):
        if not aws_access_key_id or not str(aws_access_key_id).strip():
            raise ValueError("Amazon SES aws_access_key_id is required")
        if not aws_secret_access_key or not str(aws_secret_access_key).strip():
            raise ValueError("Amazon SES aws_secret_access_key is required")
        if not from_email or not is_valid_email(from_email):
            raise ValueError(f"Invalid Amazon SES from_email: '{from_email}'")

        self._aws_access_key_id = str(aws_access_key_id).strip()
        self._aws_secret_access_key = str(aws_secret_access_key).strip()
        self._aws_session_token = str(aws_session_token).strip() if aws_session_token else None
        self.aws_region = str(aws_region).strip() or "us-east-1"
        self.from_email = from_email.strip()

        client_kwargs = {
            "region_name": self.aws_region,
            "aws_access_key_id": self._aws_access_key_id,
            "aws_secret_access_key": self._aws_secret_access_key
        }
        if self._aws_session_token:
            client_kwargs["aws_session_token"] = self._aws_session_token

        self.client = boto3.client("ses", **client_kwargs)

    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate SES email message payload."""
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
        subject = validate_no_crlf(render_template(raw_subject, template_vars), "subject")

        raw_text = data.get("message") or data.get("content") or data.get("text") or ""
        plain_content = render_template(raw_text, template_vars) if raw_text else None

        raw_html = data.get("html") or data.get("html_content") or ""
        html_content = render_template(raw_html, template_vars) if raw_html else None

        cc_list = parse_recipients(data.get("cc")) if data.get("cc") else []
        bcc_list = parse_recipients(data.get("bcc")) if data.get("bcc") else []
        reply_to = validate_no_crlf(data.get("reply_to"), "reply_to") if data.get("reply_to") else None

        attachments = validate_attachments(data.get("attachments", []))
        headers = validate_email_headers(data.get("headers", {}))

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
        """Construct a full MIME email message."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = formatted["subject"]
        msg["From"] = formatted["from_email"]
        msg["To"] = ", ".join(formatted["recipients"])

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

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch email through Amazon SES send_raw_email."""
        self.validate(message)
        formatted = self.format_message(message)

        # Build raw MIME
        mime_msg = self._build_mime_message(formatted)
        all_destinations = formatted["recipients"] + formatted["cc"] + formatted["bcc"]

        try:
            response = self.client.send_raw_email(
                Source=formatted["from_email"],
                Destinations=all_destinations,
                RawMessage={"Data": mime_msg.as_bytes()}
            )

            message_id = response.get("MessageId")

            return normalize_provider_response(
                success=True,
                provider="ses",
                channel="email",
                provider_message_id=message_id,
                status="ACCEPTED"
            )

        except ClientError as error:
            error_dict = error.response.get("Error", {})
            aws_code = error_dict.get("Code", "UnknownError")
            aws_msg = error_dict.get("Message", str(error))
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 400)

            clean_details = redact_sensitive(
                f"{aws_code}: {aws_msg}",
                [self._aws_access_key_id, self._aws_secret_access_key]
            )

            # Error Classification
            if aws_code in ("InvalidClientTokenId", "AuthFailure", "SignatureDoesNotMatch", "AccessDenied"):
                retryable = False
                error_code = "AUTH_ERROR"
            elif aws_code == "MessageRejected":
                retryable = False
                error_code = "MESSAGE_REJECTED"
            elif aws_code in ("ValidationException", "InvalidParameterValue", "InvalidParameter"):
                retryable = False
                error_code = "INVALID_PAYLOAD"
            elif aws_code in ("Throttling", "ThrottlingException", "LimitExceededException", "TooManyRequestsException"):
                retryable = True
                error_code = "RATE_LIMIT"
            elif aws_code in ("ServiceUnavailable", "InternalServiceError"):
                retryable = True
                error_code = "PROVIDER_OUTAGE"
            elif status_code >= 500:
                retryable = True
                error_code = "PROVIDER_OUTAGE"
            else:
                retryable = False
                error_code = "PROVIDER_ERROR"

            raise ProviderError(
                f"Amazon SES error [{error_code}] | Code: {aws_code} | Details: {clean_details}",
                status_code=status_code,
                retryable=retryable,
                error_code=error_code
            ) from None

        except BotoCoreError as error:
            clean_details = redact_sensitive(
                str(error),
                [self._aws_access_key_id, self._aws_secret_access_key]
            )
            raise ProviderError(
                f"Amazon SES transport error [NETWORK_ERROR] | Details: {clean_details}",
                status_code=None,
                retryable=True,
                error_code="NETWORK_ERROR"
            ) from None

        except Exception as error:
            clean_details = redact_sensitive(
                str(error),
                [self._aws_access_key_id, self._aws_secret_access_key]
            )
            raise ProviderError(
                f"Unexpected Amazon SES error [PROVIDER_ERROR] | Details: {clean_details}",
                status_code=None,
                retryable=True,
                error_code="PROVIDER_ERROR"
            ) from None

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Delivery status retrieval for SES messages."""
        return {
            "success": True,
            "provider": "ses",
            "provider_message_id": provider_message_id,
            "status": "ACCEPTED",
            "message": "Amazon SES accepted message for delivery. SNS/SES feedback updates delivery confirmation."
        }
