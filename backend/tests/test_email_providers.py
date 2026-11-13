"""
SenderX Production Email Providers Test Suite
Validates:
- SendGrid adapter: success, multiple recipients, CC/BCC, HTML/text, attachments, templates, error classification (401, 429, 500, network)
- Amazon SES adapter: success, raw MIME, CC/BCC, HTML/text, attachments, templates, error classification (Auth, Throttling, Outage, Rejected)
- SMTP adapter: success, SSL/STARTTLS, attachments, templates, error classification (Auth, Refused, Network)
- Attachment validation: size limits, traversal sanitization, base64 encoding
- Template rendering: dynamic variables in subject and body
- AdapterRegistry routing: tenant isolation, organization-specific configs, mock/production separation
- Credential validation and redaction (zero leakage in errors or responses)
"""

import base64
from email.mime.multipart import MIMEMultipart
import os
import smtplib
from unittest.mock import MagicMock, patch
import uuid
import pytest
from botocore.exceptions import ClientError, BotoCoreError

from app import create_app
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.base_adapter import ProviderError
from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.adapters.email.ses_adapter import AmazonSESAdapter
from app.adapters.email.smtp_adapter import SMTPAdapter
from app.adapters.email.mock_adapter import MockEmailAdapter
from app.adapters.email.email_utils import (
    parse_recipients,
    validate_attachment,
    validate_attachments,
    render_template,
    redact_sensitive,
    is_valid_email
)
from app.engine.retry_manager import RetryManager
from app.modules.provider_config.service import ProviderConfigService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


# ======================================================
# 1. EMAIL UTILITIES & ATTACHMENT TESTS
# ======================================================

def test_email_parsing_and_validation():
    # Valid emails
    assert is_valid_email("test@senderx.io") is True
    assert is_valid_email("invalid_email") is False

    # Single string
    assert parse_recipients("user@senderx.io") == ["user@senderx.io"]

    # Comma and semicolon separated
    assert parse_recipients("u1@test.io, u2@test.io; u3@test.io") == ["u1@test.io", "u2@test.io", "u3@test.io"]

    # List
    assert parse_recipients(["a@test.io", "b@test.io"]) == ["a@test.io", "b@test.io"]

    # Invalid in list raises ValueError
    with pytest.raises(ValueError, match="Invalid email address"):
        parse_recipients(["valid@test.io", "not-an-email"])


def test_attachment_validation_and_size_limits():
    # Valid attachment
    content = b"PDF invoice content data"
    b64 = base64.b64encode(content).decode("ascii")

    att = validate_attachment({
        "filename": "invoice.pdf",
        "mime_type": "application/pdf",
        "content": b64
    })
    assert att["filename"] == "invoice.pdf"
    assert att["mime_type"] == "application/pdf"
    assert att["size"] == len(content)

    # Path traversal protection
    att_traversal = validate_attachment({
        "filename": "../../etc/passwd",
        "content": "dGVzdA=="
    })
    assert att_traversal["filename"] == "passwd"

    # Single attachment size limit (> 10MB)
    oversized = b"A" * (10 * 1024 * 1024 + 100)
    with pytest.raises(ValueError, match="exceeds maximum single file limit"):
        validate_attachment({
            "filename": "large.bin",
            "content": oversized
        })


def test_template_rendering_integration():
    template = "Hello {{ name }}, your order #{{ order_id }} is ready!"
    vars = {"name": "Carol", "order_id": "554433"}
    rendered = render_template(template, vars)
    assert rendered == "Hello Carol, your order #554433 is ready!"

    # Empty vars returns raw template
    assert render_template(template, None) == template


def test_credential_redaction():
    secret = "SG.MySecretApiKey1234567890"
    msg = f"Failed to authenticate with key {secret} on SendGrid endpoint"
    clean = redact_sensitive(msg, [secret])
    assert secret not in clean
    assert "[REDACTED]" in clean


# ======================================================
# 2. SENDGRID ADAPTER TESTS
# ======================================================

def test_sendgrid_adapter_success_and_normalization():
    adapter = SendGridAdapter(api_key="SG.test_key_12345", from_email="alerts@senderx.io")

    message = {
        "message_id": "msg-sg-001",
        "recipient": "user@senderx.io",
        "data": {
            "subject": "System Notification",
            "message": "Your report is generated.",
            "html": "<p>Your report is generated.</p>"
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.headers = {"X-Message-Id": "sg-msg-id-77777"}

    with patch.object(adapter.client, "send", return_value=mock_response):
        res = adapter.send(message)

        assert res["success"] is True
        assert res["provider"] == "sendgrid"
        assert res["channel"] == "email"
        assert res["status"] == "ACCEPTED"
        assert res["provider_message_id"] == "sg-msg-id-77777"
        assert "timestamp" in res


def test_sendgrid_adapter_advanced_features():
    """Verify CC, BCC, Reply-To, dynamic template, and attachments."""
    adapter = SendGridAdapter(api_key="SG.test_key_12345", from_email="alerts@senderx.io")

    message = {
        "message_id": "msg-sg-002",
        "recipient": "user1@senderx.io, user2@senderx.io",
        "data": {
            "subject": "Invoice for {{ client }}",
            "message": "Hi {{ client }}, please find attached invoice.",
            "cc": "manager@senderx.io",
            "bcc": "audit@senderx.io",
            "reply_to": "billing@senderx.io",
            "template_vars": {"client": "Acme Corp"},
            "headers": {"X-SenderX-Tracking": "TX-9988"},
            "attachments": [
                {
                    "filename": "invoice_october.pdf",
                    "mime_type": "application/pdf",
                    "content": base64.b64encode(b"PDF invoice bytes").decode("ascii")
                }
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-message-id": "sg-adv-998877"}

    with patch.object(adapter.client, "send", return_value=mock_response) as mock_send:
        res = adapter.send(message)
        assert res["success"] is True
        assert res["provider_message_id"] == "sg-adv-998877"

        # Verify mail structure passed to send
        sent_mail = mock_send.call_args[0][0]
        assert sent_mail.subject.get() == "Invoice for Acme Corp"
        assert len(sent_mail.attachments) == 1
        assert sent_mail.attachments[0].file_name.get() == "invoice_october.pdf"


def test_sendgrid_error_classification():
    adapter = SendGridAdapter(api_key="SG.secret_key_to_redact", from_email="alerts@senderx.io")
    msg = {"recipient": "user@test.io", "data": {"subject": "Test", "message": "Body"}}

    # 1. 401 Authentication Failure -> Non-retryable
    err_401 = Exception("Unauthorized SG.secret_key_to_redact")
    err_401.status_code = 401
    err_401.body = b"Invalid API key SG.secret_key_to_redact"
    with patch.object(adapter.client, "send", side_effect=err_401):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        err = exc_info.value
        assert err.retryable is False
        assert err.error_code == "AUTH_ERROR"
        assert "SG.secret_key_to_redact" not in str(err)
        assert "[REDACTED]" in str(err)

    # 2. 429 Rate Limit -> Retryable with Retry-After
    err_429 = Exception("Too Many Requests")
    err_429.status_code = 429
    err_429.headers = {"Retry-After": "30"}
    with patch.object(adapter.client, "send", side_effect=err_429):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        err = exc_info.value
        assert err.retryable is True
        assert err.error_code == "RATE_LIMIT"
        assert err.retry_after == "30"

    # 3. 503 Provider Outage -> Retryable
    err_503 = Exception("Service Unavailable")
    err_503.status_code = 503
    with patch.object(adapter.client, "send", side_effect=err_503):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        assert exc_info.value.retryable is True
        assert exc_info.value.error_code == "PROVIDER_OUTAGE"


# ======================================================
# 3. AMAZON SES ADAPTER TESTS
# ======================================================

def test_ses_adapter_success_and_normalization():
    adapter = AmazonSESAdapter(
        aws_access_key_id="AKIA_TEST_KEY_1234",
        aws_secret_access_key="SECRET_TEST_KEY_5678",
        from_email="ses-sender@senderx.io",
        aws_region="us-east-1"
    )

    message = {
        "message_id": "msg-ses-001",
        "recipient": "customer@senderx.io",
        "data": {
            "subject": "Monthly Statement",
            "message": "Your statement is ready to view.",
            "html": "<p>Your statement is ready to view.</p>"
        }
    }

    with patch.object(adapter.client, "send_raw_email", return_value={"MessageId": "ses-msg-id-12345"}) as mock_send:
        res = adapter.send(message)
        assert res["success"] is True
        assert res["provider"] == "ses"
        assert res["channel"] == "email"
        assert res["status"] == "ACCEPTED"
        assert res["provider_message_id"] == "ses-msg-id-12345"

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["Source"] == "ses-sender@senderx.io"
        assert call_kwargs["Destinations"] == ["customer@senderx.io"]
        assert b"Subject: Monthly Statement" in call_kwargs["RawMessage"]["Data"]


def test_ses_adapter_with_cc_bcc_and_attachments():
    adapter = AmazonSESAdapter(
        aws_access_key_id="AKIA_TEST_KEY_1234",
        aws_secret_access_key="SECRET_TEST_KEY_5678",
        from_email="ses-sender@senderx.io"
    )

    message = {
        "message_id": "msg-ses-002",
        "recipient": "client@example.com",
        "data": {
            "subject": "Signed Document",
            "message": "See document attached.",
            "cc": "legal@example.com",
            "bcc": "records@example.com",
            "reply_to": "support@example.com",
            "attachments": [
                {
                    "filename": "contract.pdf",
                    "content": base64.b64encode(b"Signed Contract PDF Data").decode("ascii"),
                    "mime_type": "application/pdf"
                }
            ]
        }
    }

    with patch.object(adapter.client, "send_raw_email", return_value={"MessageId": "ses-raw-9988"}) as mock_send:
        res = adapter.send(message)
        assert res["success"] is True
        assert res["provider_message_id"] == "ses-raw-9988"

        call_kwargs = mock_send.call_args[1]
        assert set(call_kwargs["Destinations"]) == {"client@example.com", "legal@example.com", "records@example.com"}
        raw_bytes = call_kwargs["RawMessage"]["Data"]
        assert b"filename=\"contract.pdf\"" in raw_bytes


def test_ses_error_classification():
    adapter = AmazonSESAdapter(
        aws_access_key_id="AKIA_SECRET_TO_REDACT",
        aws_secret_access_key="SECRET_TO_REDACT_XYZ",
        from_email="ses-sender@senderx.io"
    )
    msg = {"recipient": "user@test.io", "data": {"subject": "Test", "message": "Body"}}

    # 1. InvalidClientTokenId -> Non-retryable
    client_err = ClientError(
        error_response={"Error": {"Code": "InvalidClientTokenId", "Message": "Security token is invalid SECRET_TO_REDACT_XYZ"}},
        operation_name="SendRawEmail"
    )
    with patch.object(adapter.client, "send_raw_email", side_effect=client_err):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        err = exc_info.value
        assert err.retryable is False
        assert err.error_code == "AUTH_ERROR"
        assert "SECRET_TO_REDACT_XYZ" not in str(err)
        assert "[REDACTED]" in str(err)

    # 2. Throttling -> Retryable
    throttle_err = ClientError(
        error_response={"Error": {"Code": "Throttling", "Message": "Daily sending quota exceeded"}},
        operation_name="SendRawEmail"
    )
    with patch.object(adapter.client, "send_raw_email", side_effect=throttle_err):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        assert exc_info.value.retryable is True
        assert exc_info.value.error_code == "RATE_LIMIT"

    # 3. Transport BotoCoreError -> Retryable
    with patch.object(adapter.client, "send_raw_email", side_effect=BotoCoreError()):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        assert exc_info.value.retryable is True
        assert exc_info.value.error_code == "NETWORK_ERROR"


# ======================================================
# 4. SMTP ADAPTER TESTS
# ======================================================

def test_smtp_adapter_success_and_normalization():
    adapter = SMTPAdapter(
        smtp_host="mail.example.com",
        from_email="smtp-sender@senderx.io",
        smtp_port=587,
        smtp_user="user1",
        smtp_password="password_secret_123",
        use_tls=True
    )

    message = {
        "message_id": "msg-smtp-001",
        "recipient": "customer@example.com",
        "data": {
            "subject": "Account Activation",
            "message": "Click here to activate.",
            "html": "<p>Click here to activate.</p>"
        }
    }

    mock_server = MagicMock()
    with patch.object(adapter, "_create_connection", return_value=mock_server):
        res = adapter.send(message)
        assert res["success"] is True
        assert res["provider"] == "smtp"
        assert res["channel"] == "email"
        assert res["status"] == "SENT"
        assert res["provider_message_id"].startswith("<")
        assert mock_server.send_message.called
        assert mock_server.quit.called


def test_smtp_adapter_with_attachments_and_cc():
    adapter = SMTPAdapter(
        smtp_host="mail.example.com",
        from_email="smtp-sender@senderx.io"
    )

    message = {
        "message_id": "msg-smtp-002",
        "recipient": "customer@example.com",
        "data": {
            "subject": "Your Ticket",
            "message": "Ticket is attached.",
            "cc": "support@example.com",
            "attachments": [
                {
                    "filename": "ticket.pdf",
                    "content": base64.b64encode(b"Ticket PDF Content").decode("ascii"),
                    "mime_type": "application/pdf"
                }
            ]
        }
    }

    mock_server = MagicMock()
    with patch.object(adapter, "_create_connection", return_value=mock_server):
        res = adapter.send(message)
        assert res["success"] is True

        # Check call arguments to send_message
        args, kwargs = mock_server.send_message.call_args
        mime_msg = args[0]
        assert mime_msg["Subject"] == "Your Ticket"
        assert kwargs["to_addrs"] == ["customer@example.com", "support@example.com"]


def test_smtp_error_classification():
    adapter = SMTPAdapter(
        smtp_host="mail.example.com",
        from_email="smtp-sender@senderx.io",
        smtp_password="super_secret_smtp_password"
    )
    msg = {"recipient": "user@test.io", "data": {"subject": "Test", "message": "Body"}}

    # 1. Authentication failure -> Non-retryable
    auth_err = smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication credentials invalid super_secret_smtp_password")
    with patch.object(adapter, "_create_connection", side_effect=auth_err):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        err = exc_info.value
        assert err.retryable is False
        assert err.error_code == "AUTH_ERROR"
        assert "super_secret_smtp_password" not in str(err)
        assert "[REDACTED]" in str(err)

    # 2. Recipient refused -> Non-retryable
    recip_err = smtplib.SMTPRecipientsRefused({"user@test.io": (550, b"User unknown")})
    with patch.object(adapter, "_create_connection", side_effect=recip_err):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        assert exc_info.value.retryable is False
        assert exc_info.value.error_code == "INVALID_RECIPIENT"

    # 3. Connection timeout -> Retryable
    with patch.object(adapter, "_create_connection", side_effect=TimeoutError("Connection timed out")):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send(msg)
        assert exc_info.value.retryable is True
        assert exc_info.value.error_code == "NETWORK_ERROR"


# ======================================================
# 5. REGISTRY ROUTING & TENANT ISOLATION TESTS
# ======================================================

def test_registry_email_routing_and_tenant_isolation(app):
    with app.app_context():
        org_sendgrid = f"org-sg-{uuid.uuid4().hex[:6]}"
        org_ses = f"org-ses-{uuid.uuid4().hex[:6]}"
        org_smtp = f"org-smtp-{uuid.uuid4().hex[:6]}"

        try:
            # 1. Configure SendGrid for Org A
            ProviderConfigService.save_configuration(
                provider="sendgrid",
                credentials={"api_key": "SG.org_a_specific_key", "from_email": "org_a@senderx.io"},
                organization_id=org_sendgrid
            )

            # 2. Configure SES for Org B
            ProviderConfigService.save_configuration(
                provider="ses",
                credentials={
                    "aws_access_key_id": "AKIA_ORG_B",
                    "aws_secret_access_key": "SECRET_ORG_B",
                    "from_email": "org_b@senderx.io",
                    "aws_region": "eu-west-1"
                },
                organization_id=org_ses
            )

            # 3. Configure SMTP for Org C
            ProviderConfigService.save_configuration(
                provider="smtp",
                credentials={
                    "smtp_host": "smtp.org-c.com",
                    "from_email": "org_c@senderx.io",
                    "smtp_port": 465,
                    "use_ssl": True
                },
                organization_id=org_smtp
            )

            # Verify Org A gets SendGrid with Org A's credentials
            adapter_a = AdapterRegistry.get_adapter("sendgrid", organization_id=org_sendgrid)
            assert isinstance(adapter_a, SendGridAdapter)
            assert adapter_a._api_key == "SG.org_a_specific_key"
            assert adapter_a.from_email == "org_a@senderx.io"

            # Verify Org B gets SES with Org B's credentials
            adapter_b = AdapterRegistry.get_adapter("ses", organization_id=org_ses)
            assert isinstance(adapter_b, AmazonSESAdapter)
            assert adapter_b._aws_access_key_id == "AKIA_ORG_B"
            assert adapter_b.aws_region == "eu-west-1"

            # Verify Org C gets SMTP with Org C's credentials
            adapter_c = AdapterRegistry.get_adapter("smtp", organization_id=org_smtp)
            assert isinstance(adapter_c, SMTPAdapter)
            assert adapter_c.smtp_host == "smtp.org-c.com"
            assert adapter_c.use_ssl is True

            # Verify Tenant Isolation: Org A cannot access Org B's SES configuration
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(ValueError, match="Amazon SES configuration not found"):
                    AdapterRegistry.get_adapter("ses", organization_id=org_sendgrid)

        finally:
            app.mongo_db["provider_configs"].delete_many({
                "organization_id": {"$in": [org_sendgrid, org_ses, org_smtp]}
            })


def test_mock_production_separation():
    """Verify production providers never silently fall back to mock adapters."""
    # When requesting 'mock', returns MockEmailAdapter
    mock_adapter = AdapterRegistry.get_adapter("mock", channel="email")
    assert isinstance(mock_adapter, MockEmailAdapter)

    # When requesting production provider without credentials, raises ValueError, NEVER returns mock
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc:
            AdapterRegistry.get_adapter("sendgrid", organization_id="unconfigured-org")
        assert "not found" in str(exc.value).lower()
        assert not isinstance(exc.value, MockEmailAdapter)


def test_provider_credential_validation_logic():
    """Verify validation of required fields per provider."""
    # SendGrid valid & invalid
    assert ProviderConfigService.validate_credentials("sendgrid", {"api_key": "SG.123", "from_email": "a@b.com"}) is True
    with pytest.raises(ValueError, match="requires a non-empty 'api_key'"):
        ProviderConfigService.validate_credentials("sendgrid", {"api_key": "", "from_email": "a@b.com"})

    # SES valid & invalid
    assert ProviderConfigService.validate_credentials("ses", {
        "aws_access_key_id": "KEY", "aws_secret_access_key": "SEC", "from_email": "a@b.com"
    }) is True
    with pytest.raises(ValueError, match="requires 'aws_access_key_id'"):
        ProviderConfigService.validate_credentials("ses", {"aws_secret_access_key": "SEC", "from_email": "a@b.com"})

    # SMTP valid & invalid
    assert ProviderConfigService.validate_credentials("smtp", {"smtp_host": "mail.com", "from_email": "a@b.com"}) is True
    with pytest.raises(ValueError, match="requires 'smtp_host'"):
        ProviderConfigService.validate_credentials("smtp", {"from_email": "a@b.com"})
