"""
SenderX Phase 3, Task 4: Production WhatsApp Business Cloud API Integration Test Suite
Comprehensive testing for:
- Strict Pydantic models for all WhatsApp Cloud API message types (Text, Media, Location, Interactive Buttons, Lists, CTA, Templates, Contacts)
- International phone number validation and normalization
- Media upload and MIME/file size validation
- Meta Graph API HTTP client dispatch (with mocked responses)
- Error classification (Rate limit 130429/429, internal 131000 -> retryable; token 190, undeliverable 131030, template 132000, 24h window 131047 -> permanent)
- Sensitive token and credential redaction
- Meta Webhook handshake verification (GET hub.mode, hub.challenge, hub.verify_token)
- Meta Webhook signature verification (POST X-Hub-Signature-256 HMAC-SHA256)
- Delivery receipt status updates (sent, delivered, read, failed)
- Inbound customer message capture and deduplication in MongoDB
- Multi-tenant credential isolation and Fernet encryption
- Strict mock vs production adapter separation
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
import requests
from flask_jwt_extended import create_access_token

from app import create_app
from app.adapters.base_adapter import ProviderError
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter
from app.adapters.whatsapp.mock_adapter import MockWhatsAppAdapter
from app.adapters.whatsapp.whatsapp_utils import (
    classify_whatsapp_error,
    verify_meta_signature,
    validate_media_file,
    redact_sensitive,
    normalize_whatsapp_response,
)
from app.adapters.whatsapp.models import (
    WhatsAppPayloadValidator,
    WhatsAppTextMessage,
    WhatsAppMediaItem,
    WhatsAppLocationMessage,
    WhatsAppInteractiveMessage,
    WhatsAppTemplateMessage,
    WhatsAppContactCard,
    normalize_wa_phone,
)
from app.modules.messages.repository import MessageRepository
from app.modules.messages.service import MessageService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.provider_config.service import ProviderConfigService
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = "global_verify_token_123"
    flask_app.config["WHATSAPP_APP_SECRET"] = "global_meta_app_secret_xyz"
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
            "name": f"WA Org A {suffix}",
            "slug": f"wa-org-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "WA Admin A",
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
            "email": f"wa-admin-a-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"WA Org B {suffix}",
            "slug": f"wa-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "WA Admin B",
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
            "email": f"wa-admin-b-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_a = create_access_token(
            identity=user_admin_a,
            additional_claims={
                "organization_id": org_a,
                "account_type": "ORGANIZATION_USER",
                "permissions": [
                    "organization:messages:create",
                    "organization:messages:read",
                    "organization:messages:manage",
                    "organization:providers:manage",
                    "organization:providers:read"
                ]
            }
        )

        token_b = create_access_token(
            identity=user_admin_b,
            additional_claims={
                "organization_id": org_b,
                "account_type": "ORGANIZATION_USER",
                "permissions": [
                    "organization:messages:create",
                    "organization:messages:read",
                    "organization:messages:manage",
                    "organization:providers:manage",
                    "organization:providers:read"
                ]
            }
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "token_a": token_a,
            "token_b": token_b
        }


# ===========================================================================
# 1. PYDANTIC MODELS & VALIDATION TESTS
# ===========================================================================

def test_whatsapp_phone_normalization():
    """Verify phone normalization handles various standard formats."""
    assert normalize_wa_phone("+1 (555) 123-4567") == "15551234567"
    assert normalize_wa_phone("whatsapp:+447911123456") == "447911123456"
    assert normalize_wa_phone("15551234567") == "15551234567"

    with pytest.raises(ValueError, match="Invalid WhatsApp phone number"):
        normalize_wa_phone("123")  # Too short

    with pytest.raises(ValueError, match="Invalid WhatsApp phone number"):
        normalize_wa_phone("invalid_phone_string")


def test_whatsapp_text_message_models():
    """Test WhatsApp text payload formatting and constraints."""
    # Simple text
    res = WhatsAppPayloadValidator.validate_and_format(
        recipient="+15551234567",
        data={"text": "Hello world from SenderX", "preview_url": True}
    )
    assert res["messaging_product"] == "whatsapp"
    assert res["to"] == "15551234567"
    assert res["type"] == "text"
    assert res["text"]["body"] == "Hello world from SenderX"
    assert res["text"]["preview_url"] is True

    # Exceeding 4096 characters
    with pytest.raises(ValueError):
        WhatsAppTextMessage(body="x" * 4097)


def test_whatsapp_media_models_and_limits():
    """Test media item validation (id, link, caption, limits)."""
    # Image with link
    img_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "image",
            "image": {"link": "https://example.com/photo.jpg", "caption": "Company logo"}
        }
    )
    assert img_payload["type"] == "image"
    assert img_payload["image"]["link"] == "https://example.com/photo.jpg"
    assert img_payload["image"]["caption"] == "Company logo"

    # Document with filename
    doc_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "document",
            "document": {"link": "https://example.com/contract.pdf", "filename": "Contract2026.pdf"}
        }
    )
    assert doc_payload["type"] == "document"
    assert doc_payload["document"]["filename"] == "Contract2026.pdf"

    # Missing both id and link
    with pytest.raises(ValueError, match="requires either 'id' .* or 'link'"):
        WhatsAppMediaItem(caption="No media provided")

    # Media limits check
    valid, _ = validate_media_file("image", mime_type="image/jpeg", file_size_bytes=2 * 1024 * 1024)
    assert valid is True

    valid, err = validate_media_file("image", mime_type="image/jpeg", file_size_bytes=6 * 1024 * 1024)
    assert valid is False
    assert "exceeds maximum allowed size" in err

    valid, err = validate_media_file("image", mime_type="application/pdf")
    assert valid is False
    assert "MIME type 'application/pdf' is not supported for image" in err


def test_whatsapp_location_and_contacts_models():
    """Test location coordinates and contact card models."""
    # Location
    loc_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "location",
            "location": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "name": "Headquarters",
                "address": "Market St, San Francisco, CA"
            }
        }
    )
    assert loc_payload["type"] == "location"
    assert loc_payload["location"]["latitude"] == 37.7749

    # Out-of-bounds latitude
    with pytest.raises(ValueError):
        WhatsAppLocationMessage(latitude=95.0, longitude=0.0)

    # Contacts
    contacts_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "contacts",
            "contacts": [
                {
                    "name": {"formatted_name": "Jane Doe", "first_name": "Jane", "last_name": "Doe"},
                    "phones": [{"phone": "+15551234567", "type": "WORK"}]
                }
            ]
        }
    )
    assert contacts_payload["type"] == "contacts"
    assert contacts_payload["contacts"][0]["name"]["formatted_name"] == "Jane Doe"


def test_whatsapp_interactive_reply_buttons_and_lists():
    """Test interactive reply buttons (max 3) and list messages."""
    # Valid 2 reply buttons
    btn_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Do you confirm your order?"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "btn_yes", "title": "Confirm"}},
                        {"type": "reply", "reply": {"id": "btn_no", "title": "Cancel"}}
                    ]
                }
            }
        }
    )
    assert btn_payload["type"] == "interactive"
    assert len(btn_payload["interactive"]["action"]["buttons"]) == 2

    # Reject 4 reply buttons (Meta limit is 3)
    with pytest.raises(ValueError, match="between 1 and 3"):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": "Select an option"},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": f"btn_{i}", "title": f"Option {i}"}}
                            for i in range(4)
                        ]
                    }
                }
            }
        )

    # Valid List message
    list_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": "Browse our menu"},
                "action": {
                    "button": "View Menu",
                    "sections": [
                        {
                            "title": "Beverages",
                            "rows": [
                                {"id": "item_tea", "title": "Green Tea", "description": "Organic tea"},
                                {"id": "item_coffee", "title": "Espresso", "description": "Fresh roast"}
                            ]
                        }
                    ]
                }
            }
        }
    )
    assert list_payload["interactive"]["type"] == "list"
    assert list_payload["interactive"]["action"]["button"] == "View Menu"


def test_whatsapp_meta_template_message():
    """Test Meta-approved template messages with dynamic parameters."""
    tmpl_payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "template",
            "template": {
                "name": "order_update_v2",
                "language": {"code": "en_US"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": "Kavin"},
                            {"type": "text", "text": "ORD-98765"}
                        ]
                    }
                ]
            }
        }
    )
    assert tmpl_payload["type"] == "template"
    assert tmpl_payload["template"]["name"] == "order_update_v2"
    assert tmpl_payload["template"]["language"]["code"] == "en_US"
    assert len(tmpl_payload["template"]["components"][0]["parameters"]) == 2


# ===========================================================================
# 2. ADAPTER DISPATCH & ERROR CLASSIFICATION TESTS
# ===========================================================================

def test_whatsapp_cloud_adapter_successful_dispatch():
    """Verify WhatsAppCloudAdapter sends payload and normalizes Meta Graph API response."""
    adapter = WhatsAppCloudAdapter(
        access_token="EAA_mock_token_123456",
        phone_number_id="109876543210",
        app_secret="test_secret"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "15551234567", "wa_id": "15551234567"}],
        "messages": [{"id": "wamid.HBgLMTU1NTEyMzQ1NjcVAgARGBI1RkYzQ0Q3Q0M0NTc0MEQ5MDY1M0E4"}]
    }

    with patch.object(adapter.session, "post", return_value=mock_resp) as mock_post:
        message = {
            "recipient": "+15551234567",
            "data": {
                "text": "Your appointment is confirmed!"
            }
        }
        result = adapter.send(message)

        assert result["success"] is True
        assert result["provider"] == "meta"
        assert result["channel"] == "whatsapp"
        assert result["status"] == "ACCEPTED"
        assert result["provider_message_id"] == "wamid.HBgLMTU1NTEyMzQ1NjcVAgARGBI1RkYzQ0Q3Q0M0NTc0MEQ5MDY1M0E4"
        assert mock_post.called

        # Check request URL & headers
        args, kwargs = mock_post.call_args
        assert "https://graph.facebook.com/v21.0/109876543210/messages" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer EAA_mock_token_123456"


def test_whatsapp_cloud_adapter_retryable_rate_limit_error():
    """Verify rate limit (code 130429 or HTTP 429) is classified as retryable."""
    adapter = WhatsAppCloudAdapter(
        access_token="EAA_mock_token_123456",
        phone_number_id="109876543210"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = json.dumps({
        "error": {
            "message": "Message rate limit reached",
            "type": "OAuthException",
            "code": 130429,
            "fbtrace_id": "F5qTzP..."
        }
    })
    mock_resp.json.return_value = json.loads(mock_resp.text)

    with patch.object(adapter.session, "post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send({"recipient": "+15551234567", "data": {"text": "Test"}})

        err = exc_info.value
        assert err.retryable is True
        assert err.status_code == 429
        assert err.error_code == 130429
        assert err.retry_after is not None


def test_whatsapp_cloud_adapter_permanent_errors():
    """Verify OAuth token expiry (190) and undeliverable (131030) are permanent."""
    adapter = WhatsAppCloudAdapter(
        access_token="EAA_mock_token_123456",
        phone_number_id="109876543210"
    )

    # 1. Invalid OAuth Token (190)
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = json.dumps({
        "error": {
            "message": "Error validating access token: Session has expired",
            "type": "OAuthException",
            "code": 190
        }
    })
    mock_resp.json.return_value = json.loads(mock_resp.text)

    with patch.object(adapter.session, "post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send({"recipient": "+15551234567", "data": {"text": "Test"}})
        assert exc_info.value.retryable is False

    # 2. Number not registered on WhatsApp (131030)
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 400
    mock_resp2.text = json.dumps({
        "error": {
            "message": "Recipient phone number not in allowed list or not on WhatsApp",
            "type": "OAuthException",
            "code": 131030
        }
    })
    mock_resp2.json.return_value = json.loads(mock_resp2.text)

    with patch.object(adapter.session, "post", return_value=mock_resp2):
        with pytest.raises(ProviderError) as exc_info2:
            adapter.send({"recipient": "+15551234567", "data": {"text": "Test"}})
        assert exc_info2.value.retryable is False


def test_whatsapp_cloud_adapter_token_redaction():
    """Ensure sensitive tokens and secrets are redacted from error messages."""
    token = "EAA_SECRET_ACCESS_TOKEN_XYZ123"
    adapter = WhatsAppCloudAdapter(
        access_token=token,
        phone_number_id="109876543210"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    # Simulate provider error leaking the token
    mock_resp.text = json.dumps({
        "error": {
            "message": f"Authorization failure for token {token}",
            "code": 100
        }
    })
    mock_resp.json.return_value = json.loads(mock_resp.text)

    with patch.object(adapter.session, "post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send({"recipient": "+15551234567", "data": {"text": "Test"}})

        # Token must NOT appear in plain text
        assert token not in str(exc_info.value)
        assert "EAA...123" in str(exc_info.value)


def test_whatsapp_media_upload():
    """Test media upload to Meta WhatsApp Cloud API endpoint."""
    adapter = WhatsAppCloudAdapter(
        access_token="EAA_mock_token_123456",
        phone_number_id="109876543210"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "media_987654321"}

    with patch.object(adapter.session, "post", return_value=mock_resp) as mock_post:
        file_bytes = b"%PDF-1.4 dummy pdf document content"
        media_id = adapter.upload_media(
            file_bytes=file_bytes,
            filename="statement.pdf",
            mime_type="application/pdf",
            media_type="document"
        )
        assert media_id == "media_987654321"
        assert mock_post.called
        assert "media" in mock_post.call_args[0][0]


# ===========================================================================
# 3. WEBHOOK HANDSHAKE & EVENT NOTIFICATION TESTS
# ===========================================================================

def test_whatsapp_webhook_verification_handshake(client):
    """Test GET webhook verification handshake (hub.mode & hub.verify_token)."""
    # 1. Valid handshake
    res = client.get(
        "/api/v1/messages/webhook/whatsapp?hub.mode=subscribe&hub.challenge=1122334455&hub.verify_token=global_verify_token_123"
    )
    assert res.status_code == 200
    assert res.data.decode("utf-8") == "1122334455"

    # 2. Invalid verify token
    res_bad_token = client.get(
        "/api/v1/messages/webhook/whatsapp?hub.mode=subscribe&hub.challenge=1122334455&hub.verify_token=wrong_token"
    )
    assert res_bad_token.status_code == 403

    # 3. Invalid mode
    res_bad_mode = client.get(
        "/api/v1/messages/webhook/whatsapp?hub.mode=unsubscribe&hub.challenge=1122334455&hub.verify_token=global_verify_token_123"
    )
    assert res_bad_mode.status_code == 403


def test_whatsapp_webhook_signature_verification_and_status_update(client, app, test_setup):
    """Test POST webhook signature verification and message delivery status updates."""
    org_a = test_setup["org_a"]

    with app.app_context():
        # Create a sent message to update
        test_wamid = f"wamid.HBgL{uuid.uuid4().hex}"
        msg_id = str(uuid.uuid4())

        MessageRepository.save({
            "message_id": msg_id,
            "organization_id": org_a,
            "channel": "whatsapp",
            "provider": "meta",
            "provider_message_id": test_wamid,
            "recipient": "15551234567",
            "status": "SENT",
            "data": {"text": "Appointment alert"},
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # 1. Construct valid status callback payload
        payload_data = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_1001",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550001111",
                                    "phone_number_id": "10023456789"
                                },
                                "statuses": [
                                    {
                                        "id": test_wamid,
                                        "status": "delivered",
                                        "timestamp": "1640995200",
                                        "recipient_id": "15551234567"
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }
        raw_payload = json.dumps(payload_data).encode("utf-8")

        # Compute HMAC signature using app_secret
        secret = "global_meta_app_secret_xyz"
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

        # Send POST request
        res = client.post(
            "/api/v1/messages/webhook/whatsapp",
            data=raw_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature
            }
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["processed_statuses"] >= 1

        # Verify DB status updated to DELIVERED
        updated_msg = MessageRepository.find_by_id(msg_id, organization_id=org_a)
        assert updated_msg["status"] == "DELIVERED"
        assert updated_msg["provider_status"] == "delivered"

        # 2. Test Invalid Signature rejection
        bad_res = client.post(
            "/api/v1/messages/webhook/whatsapp",
            data=raw_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid_tampered_signature_hex"
            }
        )
        assert bad_res.status_code == 401
        assert "Invalid webhook signature" in bad_res.get_json()["message"]


def test_whatsapp_inbound_customer_message_capture(client, app, test_setup):
    """Test capturing inbound customer replies with deduplication."""
    inbound_wamid = f"wamid.inbound_{uuid.uuid4().hex}"
    payload_data = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_1001",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": "10023456789"
                            },
                            "messages": [
                                {
                                    "from": "15559876543",
                                    "id": inbound_wamid,
                                    "timestamp": "1640995300",
                                    "type": "text",
                                    "text": {
                                        "body": "Yes, please reschedule to 4pm"
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw_payload = json.dumps(payload_data).encode("utf-8")
    secret = "global_meta_app_secret_xyz"
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    # Dispatch first time
    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
    )
    assert res.status_code == 200
    assert res.get_json()["processed_messages"] == 1

    # Check persistence in inbound_messages collection
    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        inbound = col.find_one({"provider_message_id": inbound_wamid})
        assert inbound is not None
        assert inbound["from_phone"] == "15559876543"
        assert inbound["content"] == "Yes, please reschedule to 4pm"

        # Dispatch second time (deduplication)
        res2 = client.post(
            "/api/v1/messages/webhook/whatsapp",
            data=raw_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature
            }
        )
        assert res2.status_code == 200
        count = col.count_documents({"provider_message_id": inbound_wamid})
        assert count == 1  # Deduplicated!


# ===========================================================================
# 4. MULTI-TENANT ISOLATION & CREDENTIAL ENCRYPTION TESTS
# ===========================================================================

def test_whatsapp_tenant_credential_isolation(client, app, test_setup):
    """Verify tenant credentials encryption at rest and strict cross-tenant isolation."""
    org_a = test_setup["org_a"]
    org_b = test_setup["org_b"]
    token_a = test_setup["token_a"]

    # 1. Org A configures WhatsApp Cloud API credentials via API
    res = client.post(
        "/api/v1/provider-config/organization",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "provider": "meta",
            "credentials": {
                "access_token": "EAA_ORG_A_SYSTEM_USER_TOKEN",
                "phone_number_id": "1009990001",
                "business_account_id": "WABA_ORG_A_1",
                "app_secret": "secret_org_a_abc",
                "webhook_verify_token": "verify_org_a"
            }
        }
    )
    assert res.status_code in (200, 201)

    with app.app_context():
        # Verify credentials encrypted at rest
        raw_doc = app.mongo_db["provider_configs"].find_one({
            "provider": "meta",
            "organization_id": org_a
        })
        assert raw_doc is not None
        assert "EAA_ORG_A_SYSTEM_USER_TOKEN" not in str(raw_doc["credentials"])
        assert raw_doc["configured"] is True

        # Verify AdapterRegistry resolves Org A adapter with Org A credentials
        adapter_a = AdapterRegistry.get_adapter(
            provider="meta",
            channel="whatsapp",
            organization_id=org_a
        )
        assert isinstance(adapter_a, WhatsAppCloudAdapter)
        assert adapter_a.access_token == "EAA_ORG_A_SYSTEM_USER_TOKEN"
        assert adapter_a.phone_number_id == "1009990001"

        # Verify Org B does NOT have Org A's credentials
        with pytest.raises(ValueError, match="WhatsApp Cloud API configuration not found"):
            AdapterRegistry.get_adapter(
                provider="meta",
                channel="whatsapp",
                organization_id=org_b
            )


def test_whatsapp_mock_vs_production_separation(app):
    """Verify requesting 'meta' never silently falls back to 'mock' adapter."""
    with app.app_context():
        # Mock adapter returns MockWhatsAppAdapter
        mock_adapter = AdapterRegistry.get_adapter(provider="mock", channel="whatsapp")
        assert isinstance(mock_adapter, MockWhatsAppAdapter)

        # Meta provider without credentials raises ValueError, NEVER falls back to mock
        with pytest.raises(ValueError, match="WhatsApp Cloud API configuration not found"):
            AdapterRegistry.get_adapter(
                provider="meta",
                channel="whatsapp",
                organization_id=str(uuid.uuid4())
            )
