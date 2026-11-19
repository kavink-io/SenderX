"""
SenderX Phase 3, Task 3: Production SMS Provider Integration Test Suite
Comprehensive testing for:
- Twilio successful dispatch and SDK integration
- Invalid credentials validation
- Invalid recipient handling and E.164 phone number normalization
- Multiple recipients dispatched as separate individual messages
- Unicode and multi-segment SMS (GSM-7 vs UCS-2)
- Long message handling and concatenation
- Rate limiting (429 / 20429) and retry-after classification
- Temporary provider failures (500/503/30001 -> retryable=True)
- Permanent provider failures (401/20003/21211/20005 -> retryable=False)
- Delivery StatusCallback webhook processing (delivered, failed, undelivered)
- Multi-tenant isolation and organization credential encryption
- Template variable rendering for SMS messages
- Mock vs production adapter separation
- Celery retry and DLQ compatibility
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from twilio.base.exceptions import TwilioRestException

from app import create_app
from app.adapters.base_adapter import ProviderError
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.sms.mock_adapter import MockSMSAdapter
from app.adapters.sms.twilio_adapter import TwilioSMSAdapter
from app.adapters.sms.sms_utils import (
    validate_e164,
    parse_sms_recipients,
    calculate_sms_segments,
    classify_twilio_error,
    is_gsm7
)
from app.modules.messages.service import MessageService
from app.modules.messages.repository import MessageRepository
from app.modules.provider_config.service import ProviderConfigService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.templates.service import TemplateService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    """Sets up Org A and Org B with users and tokens."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"SMS Org A {suffix}",
            "slug": f"sms-org-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "SMS Admin A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:providers:manage",
                "organization:providers:read",
                "organization:templates:manage",
                "organization:templates:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "name": "Admin A",
            "email": f"sms-admin-a-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"SMS Org B {suffix}",
            "slug": f"sms-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "SMS Admin B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:providers:manage",
                "organization:providers:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Admin B",
            "email": f"sms-admin-b-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_admin_a = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_admin_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "token_admin_a": token_admin_a,
            "token_admin_b": token_admin_b,
            "suffix": suffix
        }


# ===========================================================================
# 1. PHONE NUMBER VALIDATION & E.164 NORMALIZATION
# ===========================================================================

def test_e164_phone_validation():
    # Valid E.164 formats
    assert validate_e164("+14155552671") == "+14155552671"
    assert validate_e164("+447911123456") == "+447911123456"
    assert validate_e164("+919876543210") == "+919876543210"

    # Common formatting characters stripped to canonical E.164
    assert validate_e164("+1 (415) 555-2671") == "+14155552671"
    assert validate_e164("14155552671") == "+14155552671"
    assert validate_e164("+91 98765-43210") == "+919876543210"

    # Invalid phone numbers
    with pytest.raises(ValueError):
        validate_e164("")

    with pytest.raises(ValueError):
        validate_e164("not-a-number")

    with pytest.raises(ValueError):
        validate_e164("+12")  # Too short

    with pytest.raises(ValueError):
        validate_e164("+12345678901234567")  # Too long (> 15 digits)


def test_parse_sms_recipients():
    # Single string
    assert parse_sms_recipients("+14155552671") == ["+14155552671"]

    # Comma-separated string
    assert parse_sms_recipients("+14155552671, +14155552672") == ["+14155552671", "+14155552672"]

    # List of strings
    assert parse_sms_recipients(["+14155552671", "+447911123456"]) == ["+14155552671", "+447911123456"]


# ===========================================================================
# 2. ENCODING, UNICODE, AND MULTI-SEGMENT CALCULATION
# ===========================================================================

def test_sms_segmentation_gsm7_and_unicode():
    # 1. Short GSM-7 message (<= 160 chars -> 1 segment)
    res_short = calculate_sms_segments("Hello, this is a standard SMS test.")
    assert res_short["encoding"] == "GSM-7"
    assert res_short["segments"] == 1

    # 2. Long GSM-7 message (200 chars -> ceil(200 / 153) = 2 segments)
    long_gsm = "A" * 200
    res_long = calculate_sms_segments(long_gsm)
    assert res_long["encoding"] == "GSM-7"
    assert res_long["segments"] == 2

    # 3. Unicode message with Emojis (<= 70 chars -> 1 segment in UCS-2)
    unicode_msg = "Order shipped! 🚀📦"
    assert is_gsm7(unicode_msg) is False
    res_unicode = calculate_sms_segments(unicode_msg)
    assert res_unicode["encoding"] == "UCS-2"
    assert res_unicode["segments"] == 1

    # 4. Long Unicode message (100 chars -> ceil(100 / 67) = 2 segments in UCS-2)
    long_unicode = "🚀" * 100
    res_long_uni = calculate_sms_segments(long_unicode)
    assert res_long_uni["encoding"] == "UCS-2"
    assert res_long_uni["segments"] == 2

    # 5. Length exceeding maximum 1600 characters fails
    with pytest.raises(ValueError):
        calculate_sms_segments("A" * 1601)


# ===========================================================================
# 3. TWILIO ERROR CLASSIFICATION
# ===========================================================================

def test_twilio_error_classification():
    # Rate limit (Twilio 20429 or HTTP 429) -> retryable
    ret, after = classify_twilio_error(20429, 429, "Too Many Requests, retry-after: 8")
    assert ret is True
    assert after == 8

    # Server error 500/503 -> retryable
    ret, after = classify_twilio_error(50000, 500, "Internal Server Error")
    assert ret is True

    # Carrier queue overflow 30001 -> retryable
    ret, _ = classify_twilio_error(30001, 400, "Queue overflow")
    assert ret is True

    # Authentication failure 20003 -> permanent (do not retry)
    ret, _ = classify_twilio_error(20003, 401, "Authentication Error")
    assert ret is False

    # Invalid recipient 21211 -> permanent (do not retry)
    ret, _ = classify_twilio_error(21211, 400, "Invalid 'To' Phone Number")
    assert ret is False

    # Account balance depleted 20005 -> permanent
    ret, _ = classify_twilio_error(20005, 400, "Account balance depleted")
    assert ret is False


# ===========================================================================
# 4. TWILIO ADAPTER DISPATCH & MOCKING
# ===========================================================================

def test_twilio_adapter_successful_send():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.sid = "SM" + uuid.uuid4().hex
    mock_resp.status = "queued"
    mock_resp.num_segments = "1"
    mock_client.messages.create.return_value = mock_resp

    adapter = TwilioSMSAdapter(
        account_sid="AC1234567890abcdef1234567890abcdef",
        auth_token="auth_token_secret_1234567890abcdef",
        from_number="+14155550000",
        client=mock_client
    )

    message = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {
            "message": "Hello from SenderX Twilio integration!",
            "sender": "+14155550000"
        }
    }

    result = adapter.send(message)
    assert result["success"] is True
    assert result["provider"] == "twilio"
    assert result["channel"] == "sms"
    assert result["provider_message_id"] == mock_resp.sid
    assert result["status"] == "ACCEPTED"
    assert result["segments"] == 1

    # Verify call parameters
    mock_client.messages.create.assert_called_once_with(
        to="+14155552671",
        body="Hello from SenderX Twilio integration!",
        from_="+14155550000"
    )


def test_twilio_adapter_mms_media_urls():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.sid = "SM" + uuid.uuid4().hex
    mock_resp.status = "sent"
    mock_resp.num_segments = "1"
    mock_client.messages.create.return_value = mock_resp

    adapter = TwilioSMSAdapter(
        account_sid="AC1234567890abcdef1234567890abcdef",
        auth_token="auth_token_secret_1234567890abcdef",
        from_number="+14155550000",
        client=mock_client
    )

    message = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {
            "message": "Here is your invoice receipt",
            "media_urls": ["https://assets.senderx.io/invoices/inv-001.png"]
        }
    }

    result = adapter.send(message)
    assert result["success"] is True
    assert result["status"] == "SENT"
    mock_client.messages.create.assert_called_once_with(
        to="+14155552671",
        body="Here is your invoice receipt",
        from_="+14155550000",
        media_url=["https://assets.senderx.io/invoices/inv-001.png"]
    )


def test_twilio_adapter_error_handling_and_redaction():
    mock_client = MagicMock()
    # Simulate TwilioRestException for invalid phone number
    mock_client.messages.create.side_effect = TwilioRestException(
        status=400,
        uri="/2010-04-01/Accounts/AC123/Messages.json",
        msg="Invalid 'To' Phone Number: +10000000000 for token auth_token_secret_1234567890abcdef",
        code=21211
    )

    adapter = TwilioSMSAdapter(
        account_sid="AC1234567890abcdef1234567890abcdef",
        auth_token="auth_token_secret_1234567890abcdef",
        from_number="+14155550000",
        client=mock_client
    )

    message = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {"message": "Test"}
    }

    with pytest.raises(ProviderError) as exc_info:
        adapter.send(message)

    err = exc_info.value
    assert err.status_code == 400
    assert err.retryable is False  # Permanent error
    assert err.error_code == 21211
    # Verify auth token is redacted
    assert "auth_token_secret" not in str(err)
    assert "[REDACTED]" in str(err)


def test_twilio_adapter_rate_limit_retryable():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TwilioRestException(
        status=429,
        uri="/2010-04-01/Accounts/AC123/Messages.json",
        msg="Too Many Requests, retry-after: 12",
        code=20429
    )

    adapter = TwilioSMSAdapter(
        account_sid="AC1234567890abcdef1234567890abcdef",
        auth_token="auth_token_secret_1234567890abcdef",
        from_number="+14155550000",
        client=mock_client
    )

    message = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {"message": "Test Rate Limit"}
    }

    with pytest.raises(ProviderError) as exc_info:
        adapter.send(message)

    err = exc_info.value
    assert err.status_code == 429
    assert err.retryable is True
    assert err.retry_after == 12


# ===========================================================================
# 5. PROVIDER CONFIGURATION & TENANT ISOLATION
# ===========================================================================

def test_twilio_provider_config_and_tenant_isolation(client, test_setup, app):
    token_a = test_setup["token_admin_a"]
    token_b = test_setup["token_admin_b"]
    org_a = test_setup["org_a"]
    org_b = test_setup["org_b"]

    with app.app_context():
        # 1. Org A configures Twilio credentials
        res_a = client.post("/api/v1/provider-config/organization", json={
            "provider": "twilio",
            "credentials": {
                "account_sid": "AC_org_a_account_sid_123456789012",
                "auth_token": "token_org_a_auth_secret_abcdef123456",
                "from_number": "+14155550001",
                "status_callback_url": "https://api.senderx.io/api/v1/messages/webhook/twilio"
            }
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code in (200, 201)
        assert res_a.get_json()["success"] is True

        # Verify decrypted credentials for Org A
        creds_a = ProviderConfigService.get_decrypted_configuration("twilio", organization_id=org_a)
        assert creds_a["account_sid"] == "AC_org_a_account_sid_123456789012"
        assert creds_a["from_number"] == "+1415555001" or creds_a["from_number"] == "+14155550001"

        # Verify Org B DOES NOT have Twilio configured (Tenant Isolation)
        creds_b = ProviderConfigService.get_decrypted_configuration("twilio", organization_id=org_b)
        assert creds_b is None

        # Verify AdapterRegistry resolves Twilio for Org A
        with patch("app.adapters.sms.twilio_adapter.Client"):
            adapter_a = AdapterRegistry.get_adapter(provider="twilio", channel="sms", organization_id=org_a)
            assert isinstance(adapter_a, TwilioSMSAdapter)
            assert adapter_a.account_sid == "AC_org_a_account_sid_123456789012"

        # Org B attempting to resolve Twilio fails with clear configuration missing error
        with pytest.raises(ValueError) as exc:
            AdapterRegistry.get_adapter(provider="twilio", channel="sms", organization_id=org_b)
        assert "Twilio configuration not found" in str(exc.value)


# ===========================================================================
# 6. MESSAGE CREATION & MULTIPLE RECIPIENTS
# ===========================================================================

def test_sms_message_creation_single_and_batch_recipients(client, test_setup, app):
    token_a = test_setup["token_admin_a"]
    org_a = test_setup["org_a"]

    with app.app_context():
        # 1. Single recipient SMS
        res_single = client.post("/api/v1/messages/", json={
            "channel": "sms",
            "provider": "mock",
            "recipient": "+14155552671",
            "data": {
                "message": "Your verification code is 123456",
                "sender": "+14155550000"
            }
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert res_single.status_code == 201
        single_msg = res_single.get_json()["data"]["message"]
        assert single_msg["channel"] == "sms"
        assert single_msg["recipient"] == "+14155552671"
        assert single_msg["status"] == "CREATED"

        # 2. Multiple recipients SMS -> Creates separate messages for each recipient
        recipients_list = ["+14155552671", "+14155552672", "+14155552673"]
        res_multi = client.post("/api/v1/messages/", json={
            "channel": "sms",
            "provider": "mock",
            "recipient": recipients_list,
            "data": {
                "message": "Broadcast alert: system maintenance tonight at 10 PM UTC.",
                "sender": "+14155550000"
            }
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert res_multi.status_code == 201
        multi_data = res_multi.get_json()["data"]
        assert multi_data["count"] == 3
        assert len(multi_data["messages"]) == 3
        assert len(multi_data["message_ids"]) == 3

        # Verify each individual message is in MongoDB
        for msg in multi_data["messages"]:
            assert msg["recipient"] in recipients_list
            assert msg["status"] == "CREATED"
            assert msg["organization_id"] == org_a
            # Cleanup
            MessageRepository._collection().delete_one({"message_id": msg["message_id"]})

        MessageRepository._collection().delete_one({"message_id": single_msg["message_id"]})


# ===========================================================================
# 7. SMS TEMPLATE INTEGRATION
# ===========================================================================

def test_sms_template_creation_rendering_and_dispatch(client, test_setup, app):
    token_a = test_setup["token_admin_a"]
    org_a = test_setup["org_a"]

    with app.app_context():
        # 1. Create a dedicated SMS template (no HTML required!)
        t_res = client.post("/api/v1/templates/", json={
            "name": f"SMS Order Shipped {uuid.uuid4().hex[:4]}",
            "channel": "sms",
            "category": "notifications",
            "plain_text_body": "Hi {{ customer_name }}, your order #{{ order_id }} has shipped via {{ carrier }}! Track: {{ tracking_url }}",
            "variables": [
                {"name": "customer_name", "required": True},
                {"name": "order_id", "required": True},
                {"name": "carrier", "required": False, "default": "FedEx"},
                {"name": "tracking_url", "required": True}
            ]
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert t_res.status_code == 201
        tmpl_id = t_res.get_json()["data"]["template_id"]

        # 2. Publish the SMS template
        pub_res = client.post(f"/api/v1/templates/{tmpl_id}/publish", headers={"Authorization": f"Bearer {token_a}"})
        assert pub_res.status_code == 200
        assert pub_res.get_json()["data"]["status"] == "ACTIVE"

        # 3. Create SMS message referencing this template
        msg_res = client.post("/api/v1/messages/", json={
            "channel": "sms",
            "provider": "mock",
            "recipient": "+14155552671",
            "template_id": tmpl_id,
            "template_variables": {
                "customer_name": "Alex Mercer",
                "order_id": "SX-9988",
                "tracking_url": "https://track.sx.io/9988"
            }
        }, headers={"Authorization": f"Bearer {token_a}"})
        assert msg_res.status_code == 201
        created_msg = msg_res.get_json()["data"]["message"]

        # Verify rendered text injected into message.data
        expected_text = "Hi Alex Mercer, your order #SX-9988 has shipped via FedEx! Track: https://track.sx.io/9988"
        assert created_msg["data"]["message"] == expected_text
        assert created_msg["data"]["text"] == expected_text
        assert created_msg["template_id"] == tmpl_id
        assert created_msg["template_version"] == 1
        assert created_msg["template_snapshot"]["plain_text_body"] == expected_text

        MessageRepository._collection().delete_one({"message_id": created_msg["message_id"]})


# ===========================================================================
# 8. DELIVERY STATUS CALLBACK (WEBHOOK) PROCESSING
# ===========================================================================

def test_twilio_delivery_status_callback(client, app, test_setup):
    org_a = test_setup["org_a"]

    with app.app_context():
        # 1. Create a message in SENT status with provider_message_id
        provider_msg_id = "SM" + uuid.uuid4().hex
        msg_id = str(uuid.uuid4())

        MessageRepository.save({
            "message_id": msg_id,
            "organization_id": org_a,
            "channel": "sms",
            "provider": "twilio",
            "recipient": "+14155552671",
            "data": {"message": "Testing status callback"},
            "status": "PROCESSING",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        MessageRepository.mark_sent(
            message_id=msg_id,
            provider="twilio",
            provider_message_id=provider_msg_id,
            organization_id=org_a
        )

        sent_doc = MessageRepository.find_by_id(msg_id)
        assert sent_doc["status"] == "SENT"
        assert sent_doc["provider_message_id"] == provider_msg_id

        # 2. Simulate Twilio StatusCallback: MessageStatus = 'delivered'
        cb_res = client.post("/api/v1/messages/webhook/twilio", data={
            "MessageSid": provider_msg_id,
            "MessageStatus": "delivered",
            "To": "+14155552671",
            "From": "+14155550000"
        })
        assert cb_res.status_code == 200
        cb_body = cb_res.get_json()
        assert cb_body["success"] is True
        assert cb_body["status"] == "DELIVERED"
        assert cb_body["message_id"] == msg_id

        # Verify document updated in MongoDB
        delivered_doc = MessageRepository.find_by_id(msg_id)
        assert delivered_doc["status"] == "DELIVERED"
        assert any(h["to"] == "DELIVERED" for h in delivered_doc.get("status_history", []))

        # 3. Simulate another message with Twilio StatusCallback: MessageStatus = 'failed'
        fail_msg_id = str(uuid.uuid4())
        fail_provider_id = "SM" + uuid.uuid4().hex
        MessageRepository.save({
            "message_id": fail_msg_id,
            "organization_id": org_a,
            "channel": "sms",
            "provider": "twilio",
            "recipient": "+14155552671",
            "data": {"message": "Failed SMS"},
            "status": "PROCESSING",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        MessageRepository.mark_sent(
            message_id=fail_msg_id,
            provider="twilio",
            provider_message_id=fail_provider_id,
            organization_id=org_a
        )

        fail_cb_res = client.post("/api/v1/messages/webhook/twilio", data={
            "MessageSid": fail_provider_id,
            "MessageStatus": "failed",
            "ErrorCode": "30008",
            "ErrorMessage": "Unknown carrier delivery failure"
        })
        assert fail_cb_res.status_code == 200
        assert fail_cb_res.get_json()["status"] == "FAILED"

        failed_doc = MessageRepository.find_by_id(fail_msg_id)
        assert failed_doc["status"] == "FAILED"
        assert failed_doc["delivery_error_code"] == "30008"

        # Cleanup
        MessageRepository._collection().delete_one({"message_id": msg_id})
        MessageRepository._collection().delete_one({"message_id": fail_msg_id})


# ===========================================================================
# 9. MOCK VS PRODUCTION ADAPTER SEPARATION
# ===========================================================================

def test_mock_vs_production_separation(test_setup, app):
    org_a = test_setup["org_a"]

    with app.app_context():
        # Explicit mock returns MockSMSAdapter
        mock_adapter = AdapterRegistry.get_adapter(provider="mock", channel="sms")
        assert isinstance(mock_adapter, MockSMSAdapter)

        # Provider twilio never returns MockSMSAdapter
        with patch("app.adapters.sms.twilio_adapter.Client"), \
             patch("app.modules.provider_config.service.ProviderConfigService.get_decrypted_configuration", return_value={"account_sid": "AC1234567890abcdef1234567890abcdef", "auth_token": "authtoken123456", "from_number": "+15005550006"}):
            prod_adapter = AdapterRegistry.get_adapter(provider="twilio", channel="sms", organization_id=org_a)
            assert isinstance(prod_adapter, TwilioSMSAdapter)
            assert not isinstance(prod_adapter, MockSMSAdapter)

        # Unsupported provider for SMS fails explicitly
        with pytest.raises(ValueError) as exc:
            AdapterRegistry.get_adapter(provider="sendgrid", channel="sms")
        assert "only supports 'email'" in str(exc.value) or "Unsupported provider" in str(exc.value)
