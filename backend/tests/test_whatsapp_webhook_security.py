import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.messages.repository import MessageRepository
from app.modules.messages.service import MessageService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.whatsapp.repository import WhatsAppIntegrationRepository, PlatformSettingsRepository
from app.modules.whatsapp.service import PlatformSettingsService, WhatsAppEncryption
from app.modules.whatsapp.flows import WhatsAppFlowService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    # Default platform settings for the test module
    flask_app.config["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = "platform_verify_secret_token"
    flask_app.config["WHATSAPP_APP_SECRET"] = "platform_meta_app_secret_abc123"
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def fixture_data(app):
    """Sets up Org A and Org B with users and active WhatsApp integrations."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        role_a = str(uuid.uuid4())
        role_b = str(uuid.uuid4())

        pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Webhook Org A {suffix}",
            "slug": f"wa-hook-a-{suffix}",
            "status": "ACTIVE"
        })
        RoleRepository.create({
            "role_id": role_a,
            "organization_id": org_a,
            "name": "Org A Admin",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:create", "organization:messages:read"],
            "is_system_role": False
        })
        UserRepository.create({
            "user_id": user_a,
            "organization_id": org_a,
            "name": "Admin A",
            "email": f"hook-admin-a-{suffix}@test.io",
            "password_hash": pwd_hash,
            "role_ids": [role_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Webhook Org B {suffix}",
            "slug": f"wa-hook-b-{suffix}",
            "status": "ACTIVE"
        })
        RoleRepository.create({
            "role_id": role_b,
            "organization_id": org_b,
            "name": "Org B Admin",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:create", "organization:messages:read"],
            "is_system_role": False
        })
        UserRepository.create({
            "user_id": user_b,
            "organization_id": org_b,
            "name": "Admin B",
            "email": f"hook-admin-b-{suffix}@test.io",
            "password_hash": pwd_hash,
            "role_ids": [role_b],
            "is_active": True
        })

        phone_a = f"1555{uuid.uuid4().int % 10000000:07d}"
        phone_b = f"1555{uuid.uuid4().int % 10000000:07d}"
        phone_disconnected = f"1555{uuid.uuid4().int % 10000000:07d}"

        # Org A Connected Integration
        int_a = WhatsAppIntegrationRepository.create({
            "integration_id": str(uuid.uuid4()),
            "organization_id": org_a,
            "waba_id": f"WABA_A_{suffix}",
            "phone_number_id": phone_a,
            "display_phone_number": "+1 555-000-0001",
            "verified_name": "Org A WhatsApp",
            "quality_rating": "GREEN",
            "code_verification_status": "VERIFIED",
            "status": "CONNECTED",
            "onboarding_method": "MANUAL",
            "created_by": user_a
        })

        # Org B Connected Integration
        int_b = WhatsAppIntegrationRepository.create({
            "integration_id": str(uuid.uuid4()),
            "organization_id": org_b,
            "waba_id": f"WABA_B_{suffix}",
            "phone_number_id": phone_b,
            "display_phone_number": "+1 555-000-0002",
            "verified_name": "Org B WhatsApp",
            "quality_rating": "GREEN",
            "code_verification_status": "VERIFIED",
            "status": "CONNECTED",
            "onboarding_method": "MANUAL",
            "created_by": user_b
        })

        # Org B Disconnected Integration
        int_disc = WhatsAppIntegrationRepository.create({
            "integration_id": str(uuid.uuid4()),
            "organization_id": org_b,
            "waba_id": f"WABA_DISC_{suffix}",
            "phone_number_id": phone_disconnected,
            "display_phone_number": "+1 555-000-0003",
            "verified_name": "Org B Disconnected",
            "quality_rating": "UNKNOWN",
            "code_verification_status": "NOT_VERIFIED",
            "status": "DISCONNECTED",
            "onboarding_method": "MANUAL",
            "created_by": user_b
        })

        # Centralized Platform Settings Document in MongoDB
        PlatformSettingsRepository.save_setting("meta_whatsapp", {
            "meta_app_id": "meta_platform_app_999",
            "encrypted_app_secret": WhatsAppEncryption.encrypt_token("platform_meta_app_secret_abc123"),
            "encrypted_webhook_verify_token": WhatsAppEncryption.encrypt_token("platform_verify_secret_token"),
            "webhook_url": "https://api.senderx.io/api/v1/messages/webhook/whatsapp",
            "graph_api_version": "v21.0"
        })

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_a": user_a,
            "user_b": user_b,
            "phone_a": phone_a,
            "phone_b": phone_b,
            "integration_a": int_a["integration_id"],
            "phone_disconnected": phone_disconnected,
            "waba_a": f"WABA_A_{suffix}",
            "waba_b": f"WABA_B_{suffix}",
            "secret": "platform_meta_app_secret_abc123",
            "verify_token": "platform_verify_secret_token"
        }


def _sign(payload_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def test_flow_completion_webhook_data_is_encrypted_and_tenant_scoped(app, client, fixture_data, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    provider_message_id = f"wamid.flow_secure_{uuid.uuid4().hex}"
    flow_result = {"screen": "SUCCESS", "email": "private-flow@example.test"}
    raw_message = {
        "id": provider_message_id,
        "from": "15558889999",
        "timestamp": "1640995600",
        "type": "interactive",
        "interactive": {"type": "nfm_reply", "nfm_reply": {
            "name": "flow", "body": "Submitted", "response_json": json.dumps(flow_result),
        }},
    }
    event = {
        "event_id": provider_message_id,
        "event_type": "whatsapp.flow.completed",
        "organization_id": fixture_data["org_a"],
        "integration_id": fixture_data["integration_a"],
        "flow_response": flow_result,
    }
    with app.app_context():
        MessageService.save_inbound_message(
            channel="whatsapp", provider="meta", phone_number_id=fixture_data["phone_a"],
            waba_id=fixture_data["waba_a"], from_phone="15558889999",
            provider_message_id=provider_message_id, message_type="interactive",
            content=raw_message["interactive"], raw_data=raw_message, structured_event=event,
        )
        saved = app.mongo_db["inbound_messages"].find_one({"provider_message_id": provider_message_id}, {"_id": 0})
        encrypted = app.mongo_db["whatsapp_flow_responses"].find_one({"provider_message_id": provider_message_id}, {"_id": 0})
        assert saved["payload_storage_version"] == 2
        assert "flow_response" not in saved["structured_event"]
        assert "private-flow@example.test" not in str(saved)
        assert "private-flow@example.test" not in str(encrypted)
        assert saved["raw_data"]["interactive"]["nfm_reply"]["response_json"] == "[ENCRYPTED_FLOW_RESPONSE]"
        result = WhatsAppFlowService.get_completion(fixture_data["org_a"], fixture_data["integration_a"], provider_message_id)
        assert result["response"] == flow_result
        with pytest.raises(ValueError, match="Connected WhatsApp integration"):
            WhatsAppFlowService.get_completion(fixture_data["org_b"], fixture_data["integration_a"], provider_message_id)

    with app.app_context():
        org_a_token = create_access_token(
            identity=fixture_data["user_a"],
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": fixture_data["org_a"]},
        )
    response = client.get(
        f"/api/v1/whatsapp/integrations/{fixture_data['integration_a']}/flow-completions/{provider_message_id}",
        headers={"Authorization": f"Bearer {org_a_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["response"] == flow_result

    with app.app_context():
        org_b_token = create_access_token(
            identity=fixture_data["user_b"],
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": fixture_data["org_b"]},
        )
    cross_tenant = client.get(
        f"/api/v1/whatsapp/integrations/{fixture_data['integration_a']}/flow-completions/{provider_message_id}",
        headers={"Authorization": f"Bearer {org_b_token}"},
    )
    assert cross_tenant.status_code == 404


# ===========================================================================
# 1. Centralized verification-token success
# ===========================================================================

def test_centralized_verification_token_success(client, fixture_data):
    """Scenario 1: GET webhook handshake succeeds with centralized verify token."""
    token = fixture_data["verify_token"]
    res = client.get(
        f"/api/v1/messages/webhook/whatsapp?hub.mode=subscribe&hub.challenge=challenge_123456&hub.verify_token={token}"
    )
    assert res.status_code == 200
    assert res.data.decode("utf-8") == "challenge_123456"


# ===========================================================================
# 2. Incorrect verification token
# ===========================================================================

def test_incorrect_verification_token_rejected(client):
    """Scenario 2: GET webhook handshake fails with 403 on invalid verify token."""
    res = client.get(
        "/api/v1/messages/webhook/whatsapp?hub.mode=subscribe&hub.challenge=challenge_123456&hub.verify_token=wrong_token_xyz"
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert "Verification token does not match" in data["message"]


# ===========================================================================
# 3. Missing Meta App Secret (returns 503)
# ===========================================================================

def test_missing_meta_app_secret_returns_503(client, app, monkeypatch):
    """Scenario 3: POST webhook returns 503 when Meta App Secret is unconfigured."""
    # Temporarily mock PlatformSettingsService to return empty meta_app_secret
    from app.modules.whatsapp.service import PlatformSettingsService
    monkeypatch.setattr(
        PlatformSettingsService,
        "get_meta_settings",
        lambda decrypt=True, app=None: {
            "meta_app_id": "meta_app",
            "meta_app_secret": None,
            "webhook_verify_token": "some_token"
        }
    )

    dummy_payload = json.dumps({"object": "whatsapp_business_account"}).encode("utf-8")
    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=dummy_payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=abcdef1234567890"
        }
    )
    assert res.status_code == 503
    data = res.get_json()
    assert data["success"] is False
    assert "Meta App Secret is not configured" in data["message"]


# ===========================================================================
# 4. Missing signature header (returns 401)
# ===========================================================================

def test_missing_signature_header_returns_401(client):
    """Scenario 4: POST webhook returns 401 when X-Hub-Signature-256 header is missing."""
    dummy_payload = json.dumps({"object": "whatsapp_business_account"}).encode("utf-8")
    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=dummy_payload,
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert "Missing X-Hub-Signature-256 header" in data["message"]


# ===========================================================================
# 5. Invalid signature (returns 401)
# ===========================================================================

def test_invalid_signature_returns_401(client):
    """Scenario 5: POST webhook returns 401 when signature is invalid or tampered."""
    dummy_payload = json.dumps({"object": "whatsapp_business_account"}).encode("utf-8")
    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=dummy_payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        }
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert "Invalid webhook signature" in data["message"]


# ===========================================================================
# 6. Valid signature (returns 200)
# ===========================================================================

def test_valid_signature_returns_200(client, fixture_data):
    """Scenario 6: POST webhook with valid HMAC signature succeeds with 200."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": []
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["processed_statuses"] == 0
    assert data["processed_messages"] == 0


# ===========================================================================
# 7. Correct phone-number-to-organization resolution
# ===========================================================================

def test_correct_phone_number_to_org_resolution(client, app, fixture_data):
    """Scenario 7: Inbound message resolves tenant organization strictly via active phone_number_id."""
    org_a = fixture_data["org_a"]
    phone_a = fixture_data["phone_a"]
    waba_a = fixture_data["waba_a"]
    msg_wamid = f"wamid.inbound_{uuid.uuid4().hex}"

    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_a,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_a
                            },
                            "messages": [
                                {
                                    "from": "15559871111",
                                    "id": msg_wamid,
                                    "timestamp": "1640995000",
                                    "type": "text",
                                    "text": {"body": "Hello Org A Support"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["processed_messages"] == 1

    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        saved = col.find_one({"provider_message_id": msg_wamid})
        assert saved is not None
        assert saved["organization_id"] == org_a
        assert saved["phone_number_id"] == phone_a
        assert saved["channel"] == "whatsapp"
        assert saved["provider"] == "meta"
        assert saved["content"] == "Hello Org A Support"


# ===========================================================================
# 8. Unknown phone number (rejected, no message saved)
# ===========================================================================

def test_unknown_phone_number_rejected_and_not_saved(client, app, fixture_data):
    """Scenario 8: Inbound message for unknown phone_number_id is rejected and never saved to DB."""
    unknown_phone = "19999999999"
    msg_wamid = f"wamid.unknown_{uuid.uuid4().hex}"

    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_UNKNOWN",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": unknown_phone
                            },
                            "messages": [
                                {
                                    "from": "15559872222",
                                    "id": msg_wamid,
                                    "timestamp": "1640995100",
                                    "type": "text",
                                    "text": {"body": "Spam to unknown number"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["processed_messages"] == 0

    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        saved = col.find_one({"provider_message_id": msg_wamid})
        assert saved is None


# ===========================================================================
# 9. Disconnected integration (rejected, no message saved)
# ===========================================================================

def test_disconnected_integration_rejected(client, app, fixture_data):
    """Scenario 9: Inbound message for non-connected integration is rejected and not saved."""
    phone_disc = fixture_data["phone_disconnected"]
    msg_wamid = f"wamid.disc_{uuid.uuid4().hex}"

    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_DISC",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_disc
                            },
                            "messages": [
                                {
                                    "from": "15559873333",
                                    "id": msg_wamid,
                                    "timestamp": "1640995200",
                                    "type": "text",
                                    "text": {"body": "Hello to disconnected number"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["processed_messages"] == 0

    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        saved = col.find_one({"provider_message_id": msg_wamid})
        assert saved is None


# ===========================================================================
# 10. Cross-tenant delivery-status isolation
# ===========================================================================

def test_cross_tenant_delivery_status_isolation(client, app, fixture_data):
    """Scenario 10: Status update webhook with Org A's phone_number_id cannot update Org B's message."""
    org_a = fixture_data["org_a"]
    org_b = fixture_data["org_b"]
    phone_a = fixture_data["phone_a"]
    phone_b = fixture_data["phone_b"]

    wamid_b = f"wamid.org_b_msg_{uuid.uuid4().hex}"
    msg_b_id = str(uuid.uuid4())

    with app.app_context():
        # Save a message belonging strictly to Org B
        MessageRepository.save({
            "message_id": msg_b_id,
            "organization_id": org_b,
            "channel": "whatsapp",
            "provider": "meta",
            "provider_message_id": wamid_b,
            "recipient": "15554440000",
            "status": "SENT",
            "data": {"text": "Org B private invoice"},
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    # Tampered webhook: Status event targets Org B's wamid, but payload specifies Org A's phone_number_id
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": fixture_data["waba_a"],
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_a  # Resolves to Org A!
                            },
                            "statuses": [
                                {
                                    "id": wamid_b,
                                    "status": "delivered",
                                    "timestamp": "1640995300",
                                    "recipient_id": "15554440000"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    res = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )
    assert res.status_code == 200

    with app.app_context():
        # Org B's message must NOT have been modified by Org A's phone_number_id event!
        msg_b = MessageRepository.find_by_id(msg_b_id, organization_id=org_b)
        assert msg_b["status"] == "SENT"
        assert msg_b.get("provider_status") != "delivered"


# ===========================================================================
# 11. Duplicate webhook event handling (no duplicate status history)
# ===========================================================================

def test_duplicate_webhook_events_prevent_duplicate_status_history(client, app, fixture_data):
    """Scenario 11: Duplicate webhook status updates do not create duplicate entries in status_history."""
    org_a = fixture_data["org_a"]
    phone_a = fixture_data["phone_a"]
    wamid_dup = f"wamid.status_dup_{uuid.uuid4().hex}"
    msg_id = str(uuid.uuid4())

    with app.app_context():
        MessageRepository.save({
            "message_id": msg_id,
            "organization_id": org_a,
            "channel": "whatsapp",
            "provider": "meta",
            "provider_message_id": wamid_dup,
            "recipient": "15555550001",
            "status": "SENT",
            "status_history": [
                {
                    "from": "QUEUED",
                    "to": "SENT",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "worker"
                }
            ],
            "data": {"text": "Hello dup test"},
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": fixture_data["waba_a"],
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_a
                            },
                            "statuses": [
                                {
                                    "id": wamid_dup,
                                    "status": "delivered",
                                    "timestamp": "1640995400",
                                    "recipient_id": "15555550001"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    # First delivery: updates status to DELIVERED
    res1 = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig}
    )
    assert res1.status_code == 200
    assert res1.get_json()["processed_statuses"] == 1

    with app.app_context():
        msg = MessageRepository.find_by_id(msg_id, organization_id=org_a)
        assert msg["status"] == "DELIVERED"
        history_len_after_first = len(msg.get("status_history", []))
        assert history_len_after_first == 2  # initial + delivered

    # Second delivery with identical event payload
    res2 = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig}
    )
    assert res2.status_code == 200
    assert res2.get_json()["processed_statuses"] == 1

    with app.app_context():
        msg_after_second = MessageRepository.find_by_id(msg_id, organization_id=org_a)
        assert msg_after_second["status"] == "DELIVERED"
        history_len_after_second = len(msg_after_second.get("status_history", []))
        # Crucial assertion: status_history length must not have increased on duplicate
        assert history_len_after_second == history_len_after_first


# ===========================================================================
# 12. Existing inbound message behavior & deduplication
# ===========================================================================

def test_inbound_message_deduplication(client, app, fixture_data):
    """Scenario 12: Inbound messages are deduplicated by provider_message_id without duplicate entries."""
    org_a = fixture_data["org_a"]
    phone_a = fixture_data["phone_a"]
    inbound_wamid = f"wamid.inbound_idempotency_{uuid.uuid4().hex}"

    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": fixture_data["waba_a"],
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": phone_a
                            },
                            "messages": [
                                {
                                    "from": "15558889999",
                                    "id": inbound_wamid,
                                    "timestamp": "1640995500",
                                    "type": "text",
                                    "text": {"body": "First delivery of inbound"}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = _sign(raw, fixture_data["secret"])

    # First delivery
    res1 = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig}
    )
    assert res1.status_code == 200
    assert res1.get_json()["processed_messages"] == 1

    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        count1 = col.count_documents({"provider_message_id": inbound_wamid})
        assert count1 == 1

    # Second delivery of same message
    res2 = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig}
    )
    assert res2.status_code == 200

    with app.app_context():
        col = app.mongo_db["inbound_messages"]
        count2 = col.count_documents({"provider_message_id": inbound_wamid})
        # Crucial assertion: exactly one inbound document exists
        assert count2 == 1


@pytest.mark.parametrize(
    ("reply_type", "reply_data", "expected_event_type"),
    [
        ("button_reply", {"id": "confirm", "title": "Confirm"}, "whatsapp.button_reply"),
        (
            "list_reply",
            {"id": "menu_coffee", "title": "Coffee", "description": "Fresh roast"},
            "whatsapp.list_reply",
        ),
    ],
)
def test_interactive_reply_webhook_normalizes_event_and_preserves_payload(
    client, app, fixture_data, reply_type, reply_data, expected_event_type
):
    inbound_wamid = f"wamid.interactive_{uuid.uuid4().hex}"
    message = {
        "from": "15558889999",
        "id": inbound_wamid,
        "timestamp": "1640995600",
        "type": "interactive",
        "interactive": {"type": reply_type, reply_type: reply_data},
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [message],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )

    assert response.status_code == 200
    assert response.get_json()["processed_messages"] == 1
    with app.app_context():
        saved = app.mongo_db["inbound_messages"].find_one({"provider_message_id": inbound_wamid}, {"_id": 0})
        assert saved["organization_id"] == fixture_data["org_a"]
        assert saved["integration_id"]
        assert saved["message_type"] == "interactive"
        assert saved["event_type"] == expected_event_type
        assert saved["structured_event"]["selection"]["id"] == reply_data["id"]
        assert saved["structured_event"]["selection"]["title"] == reply_data["title"]
        assert saved["raw_data"] == message
        if reply_type == "list_reply":
            assert saved["structured_event"]["selection"]["description"] == "Fresh roast"


def test_interactive_reply_webhook_is_idempotent(client, app, fixture_data):
    inbound_wamid = f"wamid.interactive_duplicate_{uuid.uuid4().hex}"
    message = {
        "from": "15558889999",
        "id": inbound_wamid,
        "timestamp": "1640995700",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "yes", "title": "Yes"}},
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [message],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": _sign(raw, fixture_data["secret"]),
    }

    first = client.post("/api/v1/messages/webhook/whatsapp", data=raw, headers=headers)
    second = client.post("/api/v1/messages/webhook/whatsapp", data=raw, headers=headers)
    assert first.status_code == second.status_code == 200
    with app.app_context():
        assert app.mongo_db["inbound_messages"].count_documents({"provider_message_id": inbound_wamid}) == 1


def test_unknown_interactive_reply_is_preserved_as_unknown_event(client, app, fixture_data):
    inbound_wamid = f"wamid.interactive_unknown_{uuid.uuid4().hex}"
    message = {
        "from": "15558889999",
        "id": inbound_wamid,
        "timestamp": "1640995800",
        "type": "interactive",
        "interactive": {"type": "future_reply_type", "future_reply_type": {"opaque": "value"}},
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [message],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )

    assert response.status_code == 200
    assert response.get_json()["processed_messages"] == 1
    with app.app_context():
        saved = app.mongo_db["inbound_messages"].find_one({"provider_message_id": inbound_wamid}, {"_id": 0})
        assert saved["event_type"] == "whatsapp.interactive.unknown"
        assert saved["structured_event"]["unrecognized_type"] == "future_reply_type"
        assert saved["structured_event"]["selection"] is None
        assert saved["raw_data"] == message


def test_interactive_reply_waba_mismatch_is_rejected(client, app, fixture_data):
    inbound_wamid = f"wamid.interactive_wrong_waba_{uuid.uuid4().hex}"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_b"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [{
                        "from": "15558889999",
                        "id": inbound_wamid,
                        "timestamp": "1640995900",
                        "type": "interactive",
                        "interactive": {"type": "button_reply", "button_reply": {"id": "yes", "title": "Yes"}},
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )

    assert response.status_code == 200
    assert response.get_json()["processed_messages"] == 0
    with app.app_context():
        assert app.mongo_db["inbound_messages"].find_one({"provider_message_id": inbound_wamid}) is None


def test_duplicate_provider_message_id_cannot_cross_tenants(client, app, fixture_data):
    inbound_wamid = f"wamid.cross_tenant_duplicate_{uuid.uuid4().hex}"

    def signed_payload(waba_id, phone_number_id, message):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": waba_id,
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": phone_number_id},
                        "messages": [message],
                    },
                    "field": "messages",
                }],
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        return raw, {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(raw, fixture_data["secret"]),
        }

    message_a = {
        "from": "15558889999", "id": inbound_wamid, "timestamp": "1640996000",
        "type": "text", "text": {"body": "Org A message"},
    }
    raw_a, headers_a = signed_payload(fixture_data["waba_a"], fixture_data["phone_a"], message_a)
    response_a = client.post("/api/v1/messages/webhook/whatsapp", data=raw_a, headers=headers_a)
    assert response_a.get_json()["processed_messages"] == 1

    message_b = {
        "from": "15558889998", "id": inbound_wamid, "timestamp": "1640996001",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "ok", "title": "OK"}},
    }
    raw_b, headers_b = signed_payload(fixture_data["waba_b"], fixture_data["phone_b"], message_b)
    response_b = client.post("/api/v1/messages/webhook/whatsapp", data=raw_b, headers=headers_b)
    assert response_b.get_json()["processed_messages"] == 0

    with app.app_context():
        records = list(app.mongo_db["inbound_messages"].find({"provider_message_id": inbound_wamid}, {"_id": 0}))
        assert len(records) == 1
        assert records[0]["organization_id"] == fixture_data["org_a"]
        assert records[0]["raw_data"] == message_a


def test_whatsapp_signature_uses_exact_raw_request_bytes(client, fixture_data):
    raw = b' { "object" : "whatsapp_business_account", "entry" : [] }\n'
    valid = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )
    assert valid.status_code == 200

    canonical = json.dumps(json.loads(raw)).encode("utf-8")
    invalid = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(canonical, fixture_data["secret"])},
    )
    assert invalid.status_code == 401


def test_webhook_acknowledges_malformed_siblings_and_processes_valid_message(client, app, fixture_data):
    valid_message = {
        "from": "15558889999",
        "id": f"wamid.mixed_valid_{uuid.uuid4().hex}",
        "timestamp": "1640996100",
        "type": "text",
        "text": {"body": "Sibling survives malformed event"},
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [None, {"type": "text", "text": {"body": "missing ID"}}, valid_message],
                    "statuses": [None, {"id": "", "status": "delivered"}],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["processed_messages"] == 1
    assert body["processed_statuses"] == 0
    assert body["ignored_events"] >= 4
    with app.app_context():
        saved = app.mongo_db["inbound_messages"].find_one({"provider_message_id": valid_message["id"]})
        assert saved is not None
        assert saved["content"] == "Sibling survives malformed event"


def test_transient_event_failure_retries_batch_after_processing_siblings(client, app, fixture_data, monkeypatch):
    from pymongo.errors import AutoReconnect

    first_message = {
        "from": "15558889999", "id": f"wamid.retry_first_{uuid.uuid4().hex}",
        "timestamp": "1640996200", "type": "text", "text": {"body": "Retry me"},
    }
    second_message = {
        "from": "15558889998", "id": f"wamid.retry_second_{uuid.uuid4().hex}",
        "timestamp": "1640996201", "type": "text", "text": {"body": "Process sibling"},
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "messages": [first_message, second_message],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": _sign(raw, fixture_data["secret"]),
    }
    original_save = MessageService.save_inbound_message
    attempted = set()

    def fail_first_temporarily(cls, **kwargs):
        if kwargs["provider_message_id"] == first_message["id"] and first_message["id"] not in attempted:
            attempted.add(first_message["id"])
            raise AutoReconnect("temporary database disconnect")
        return original_save(**kwargs)

    monkeypatch.setattr(MessageService, "save_inbound_message", classmethod(fail_first_temporarily))
    response = client.post("/api/v1/messages/webhook/whatsapp", data=raw, headers=headers)
    assert response.status_code == 503
    assert response.get_json()["processed_messages"] == 1
    assert response.get_json()["retryable_failures"] == 1

    retry = client.post("/api/v1/messages/webhook/whatsapp", data=raw, headers=headers)
    assert retry.status_code == 200
    with app.app_context():
        assert app.mongo_db["inbound_messages"].count_documents({"provider_message_id": first_message["id"]}) == 1
        assert app.mongo_db["inbound_messages"].count_documents({"provider_message_id": second_message["id"]}) == 1


def test_webhook_status_callbacks_never_regress_read_state(client, app, fixture_data):
    org_id = fixture_data["org_a"]
    wamid = f"wamid.monotonic_{uuid.uuid4().hex}"
    message_id = str(uuid.uuid4())
    with app.app_context():
        MessageRepository.save({
            "message_id": message_id,
            "organization_id": org_id,
            "channel": "whatsapp",
            "provider": "meta",
            "provider_message_id": wamid,
            "recipient": "15555550001",
            "status": "SENT",
            "status_history": [{"from": "PROCESSING", "to": "SENT", "timestamp": datetime.now(timezone.utc).isoformat()}],
            "data": {"text": "Monotonic status test"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    statuses = ["delivered", "sent", "read", "delivered", "sent"]
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": fixture_data["waba_a"],
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": fixture_data["phone_a"]},
                    "statuses": [{"id": wamid, "status": status, "timestamp": str(index)} for index, status in enumerate(statuses)],
                },
                "field": "messages",
            }],
        }],
    }
    raw = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )

    assert response.status_code == 200
    assert response.get_json()["processed_statuses"] == 2
    with app.app_context():
        saved = MessageRepository.find_by_id(message_id, organization_id=org_id)
        assert saved["status"] == "READ"
        assert len(saved["status_history"]) == 3


def test_webhook_invalid_json_is_rejected_after_raw_signature_check(client, fixture_data):
    raw = b'{not-json'
    response = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, fixture_data["secret"])},
    )
    assert response.status_code == 400
    unauthenticated = client.post(
        "/api/v1/messages/webhook/whatsapp",
        data=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalid"},
    )
    assert unauthenticated.status_code == 401


def test_webhook_verification_rejects_missing_challenge(client, fixture_data):
    response = client.get(
        "/api/v1/messages/webhook/whatsapp?hub.mode=subscribe&hub.verify_token="
        + fixture_data["verify_token"]
    )
    assert response.status_code == 400
    assert "hub.challenge is required" in response.get_json()["message"]
