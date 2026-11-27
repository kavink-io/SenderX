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
from app.adapters.errors import ProviderResolutionError
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

        # Register Org A WhatsApp Integration for multi-tenant webhook tests
        from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
        WhatsAppIntegrationRepository.create({
            "integration_id": str(uuid.uuid4()),
            "organization_id": org_a,
            "waba_id": "WABA_1001",
            "phone_number_id": "10023456789",
            "display_phone_number": "+15550001111",
            "verified_name": "Org A Business",
            "quality_rating": "GREEN",
            "code_verification_status": "VERIFIED",
            "status": "CONNECTED",
            "onboarding_method": "MANUAL",
            "created_by": user_admin_a
        })

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


@pytest.mark.parametrize(
    ("media_type", "url"),
    [
        ("image", "https://example.com/photo.jpg"),
        ("video", "https://example.com/clip.mp4"),
        ("audio", "https://example.com/voice.ogg"),
        ("document", "https://example.com/report.pdf"),
    ],
)
def test_whatsapp_explicit_media_url_alias_infers_and_maps_type(media_type, url):
    """Dedicated media URL aliases infer the corresponding Meta message type."""
    payload = WhatsAppPayloadValidator.validate_and_format(
        message={
            "recipient": "+15551234567",
            "data": {f"{media_type}_url": url},
        }
    )

    assert payload["type"] == media_type
    assert payload[media_type]["link"] == url


def test_whatsapp_media_url_alias_requires_unambiguous_type():
    with pytest.raises(ValueError, match="Could not determine WhatsApp message type"):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="+15551234567",
            data={"media_url": "https://example.com/file"},
        )

    with pytest.raises(ValueError, match="only one type-specific"):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="+15551234567",
            data={
                "image_url": "https://example.com/photo.jpg",
                "video_url": "https://example.com/clip.mp4",
            },
        )


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


def test_whatsapp_single_product_payload_mapping_and_optional_content():
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "product",
                "action": {
                    "catalog_id": "1234567890123",
                    "product_retailer_id": "SKU-RED-42",
                },
            },
        },
    )
    assert payload["type"] == "interactive"
    assert payload["interactive"] == {
        "type": "product",
        "action": {"catalog_id": "1234567890123", "product_retailer_id": "SKU-RED-42"},
    }

    with_optional_content = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "product",
                "body": {"text": "A product for you"},
                "footer": {"text": "While supplies last"},
                "action": {"catalog_id": "1234567890123", "product_retailer_id": "SKU-RED-42"},
            },
        },
    )
    assert with_optional_content["interactive"]["body"] == {"text": "A product for you"}
    assert with_optional_content["interactive"]["footer"] == {"text": "While supplies last"}


@pytest.mark.parametrize(
    ("action", "error"),
    [
        ({"product_retailer_id": "SKU-RED-42"}, "numeric catalog_id"),
        ({"catalog_id": "1234567890123"}, "non-empty product_retailer_id"),
        ({"catalog_id": "not-numeric", "product_retailer_id": "SKU-RED-42"}, "numeric catalog_id"),
        ({"catalog_id": "1234567890123", "product_retailer_id": "  "}, "non-empty product_retailer_id"),
    ],
)
def test_whatsapp_single_product_rejects_invalid_identifiers(action, error):
    with pytest.raises(ValueError, match=error):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={"type": "interactive", "interactive": {"type": "product", "action": action}},
        )


def test_whatsapp_unknown_interactive_type_is_rejected():
    with pytest.raises(ValueError, match="type"):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={"type": "interactive", "interactive": {"type": "made_up", "action": {}}},
        )


def _product_list_payload(product_count=2, sections=None):
    products = [
        {"product_retailer_id": f"sku-{index}"}
        for index in range(product_count)
    ]
    return {
        "type": "interactive",
        "interactive": {
            "type": "product_list",
            "header": {"type": "text", "text": "Featured products"},
            "body": {"text": "Choose a product"},
            "footer": {"text": "Availability varies"},
            "action": {
                "catalog_id": "1234567890123",
                "sections": sections if sections is not None else [{"title": "Featured", "product_items": products}],
            },
        },
    }


def test_whatsapp_multi_product_maps_multiple_sections_and_accepts_30_items():
    sections = [
        {"title": "First", "product_items": [{"product_retailer_id": "sku-1"}]},
        {"title": "Second", "product_items": [{"product_retailer_id": f"sku-{i}"} for i in range(2, 31)]},
    ]
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567", data=_product_list_payload(30, sections)
    )
    interactive = payload["interactive"]
    assert interactive["type"] == "product_list"
    assert interactive["header"] == {"type": "text", "text": "Featured products"}
    assert interactive["action"]["catalog_id"] == "1234567890123"
    assert len(interactive["action"]["sections"]) == 2
    assert sum(len(section["product_items"]) for section in interactive["action"]["sections"]) == 30


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (_product_list_payload(31), "at most 30"),
        (_product_list_payload(0, [{"title": "Empty", "product_items": []}]), "at least one product"),
        (_product_list_payload(1, [{"title": "Bad", "product_items": [{"product_retailer_id": " "}]}]), "non-empty product_retailer_id"),
        (_product_list_payload(1, [{"title": "A" * 25, "product_items": [{"product_retailer_id": "sku"}]}]), "titles must be 1-24"),
    ],
)
def test_whatsapp_multi_product_rejects_invalid_sections_and_boundaries(data, error):
    with pytest.raises(ValueError, match=error):
        WhatsAppPayloadValidator.validate_and_format(recipient="15551234567", data=data)


def test_whatsapp_multi_product_requires_text_header_and_body():
    data = _product_list_payload()
    data["interactive"].pop("header")
    with pytest.raises(ValueError, match="text header"):
        WhatsAppPayloadValidator.validate_and_format(recipient="15551234567", data=data)

    data = _product_list_payload()
    data["interactive"].pop("body")
    with pytest.raises(ValueError, match="require a body"):
        WhatsAppPayloadValidator.validate_and_format(recipient="15551234567", data=data)


def test_whatsapp_full_catalog_mapping_and_thumbnail_validation():
    data = {
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": "Browse our catalog"},
            "footer": {"text": "Tap to explore"},
            "action": {"name": "catalog_message", "parameters": {"thumbnail_product_retailer_id": "SKU-1"}},
        },
    }
    payload = WhatsAppPayloadValidator.validate_and_format(recipient="15551234567", data=data)
    assert payload["interactive"]["action"] == {
        "name": "catalog_message",
        "parameters": {"thumbnail_product_retailer_id": "SKU-1"},
    }

    data["interactive"]["action"]["parameters"]["thumbnail_product_retailer_id"] = "  "
    with pytest.raises(ValueError, match="non-empty product_retailer_id"):
        WhatsAppPayloadValidator.validate_and_format(recipient="15551234567", data=data)


def test_whatsapp_product_catalog_dispatch_uses_selected_integration_catalog(app, test_setup):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
    from app.queue.tasks import process_message

    org_id = test_setup["org_a"]
    with app.app_context():
        integration = _get_test_whatsapp_integration(org_id)
        WhatsAppIntegrationRepository.update(
            integration["integration_id"], org_id, {"catalog_id": "999888777666"}
        )
        message = {
            "message_id": "catalog-dispatch-" + uuid.uuid4().hex,
            "organization_id": org_id,
            "channel": "whatsapp",
            "provider": "meta",
            "recipient": "15559876543",
            "integration_id": integration["integration_id"],
            "data": {"type": "interactive", "interactive": {
                "type": "product", "action": {
                    "catalog_id": "999888777666", "product_retailer_id": "sku-1"
                }
            }},
            "status": "QUEUED", "retry_count": 0,
        }
        adapter = MagicMock()
        adapter.send.return_value = {"success": True, "provider": "meta", "provider_message_id": "wamid.catalog"}
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_sent", return_value=True), \
             patch("app.modules.dead_letters.repository.DeadLetterRepository.find_by_message_id", return_value=None), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter", return_value=adapter), \
             patch.object(MessageService, "check_whatsapp_customer_service_window", return_value={"allowed": True}):
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is True
    dispatched = adapter.send.call_args.args[0]["data"]["interactive"]["action"]
    assert dispatched["catalog_id"] == "999888777666"


def test_whatsapp_product_catalog_dispatch_rejects_missing_or_cross_integration_catalog(app, test_setup):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
    from app.queue.tasks import process_message

    org_id = test_setup["org_a"]
    with app.app_context():
        integration = _get_test_whatsapp_integration(org_id)
        WhatsAppIntegrationRepository.update(integration["integration_id"], org_id, {"catalog_id": "111222333444"})
        message = {
            "message_id": "catalog-reject-" + uuid.uuid4().hex,
            "organization_id": org_id, "channel": "whatsapp", "provider": "meta",
            "recipient": "15559876543", "integration_id": integration["integration_id"],
            "data": {"type": "interactive", "interactive": {
                "type": "product", "action": {
                    "catalog_id": "999888777666", "product_retailer_id": "sku-1"
                }
            }},
            "status": "QUEUED", "retry_count": 0,
        }
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_failed", return_value=True), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as make_adapter:
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is False
    make_adapter.assert_not_called()


def test_whatsapp_product_catalog_dispatch_rejects_missing_tenant_catalog(app, test_setup):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
    from app.queue.tasks import process_message

    org_id = test_setup["org_a"]
    with app.app_context():
        integration = _get_test_whatsapp_integration(org_id)
        WhatsAppIntegrationRepository.update(integration["integration_id"], org_id, {"catalog_id": None})
        message = {
            "message_id": "catalog-unconfigured-" + uuid.uuid4().hex,
            "organization_id": org_id, "channel": "whatsapp", "provider": "meta",
            "recipient": "15559876543", "integration_id": integration["integration_id"],
            "data": {"type": "interactive", "interactive": {
                "type": "product", "action": {
                    "catalog_id": "999888777666", "product_retailer_id": "sku-1"
                }
            }},
            "status": "QUEUED", "retry_count": 0,
        }
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_failed", return_value=True), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as make_adapter:
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is False
    make_adapter.assert_not_called()


def test_whatsapp_product_catalog_dispatch_rejects_other_organization_integration(app, test_setup):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
    from app.queue.tasks import process_message

    org_a, org_b = test_setup["org_a"], test_setup["org_b"]
    with app.app_context():
        other_tenant_integration_id = "wai-cross-tenant-" + uuid.uuid4().hex
        message = {
            "message_id": "catalog-cross-org-" + uuid.uuid4().hex,
            "organization_id": org_a, "channel": "whatsapp", "provider": "meta",
            "recipient": "15559876543", "integration_id": other_tenant_integration_id,
            "data": {"type": "interactive", "interactive": {
                "type": "product", "action": {
                    "catalog_id": "999888777666", "product_retailer_id": "sku-1"
                }
            }},
            "status": "QUEUED", "retry_count": 0,
        }
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_failed", return_value=True), \
             patch("app.modules.whatsapp.repository.WhatsAppIntegrationRepository.find_by_id", return_value=None) as find_integration, \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as make_adapter:
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is False
    make_adapter.assert_not_called()
    assert any(call.kwargs.get("organization_id") == org_a for call in find_integration.call_args_list)


def test_whatsapp_catalog_configuration_is_numeric_clearable_and_tenant_scoped(app, test_setup):
    from app.modules.whatsapp.models import WhatsAppIntegrationUpdateSchema
    from app.modules.whatsapp.service import WhatsAppIntegrationService

    assert WhatsAppIntegrationUpdateSchema(catalog_id="123456789").catalog_id == "123456789"
    cleared = WhatsAppIntegrationUpdateSchema(catalog_id=None)
    assert "catalog_id" in cleared.model_fields_set and cleared.catalog_id is None
    with pytest.raises(ValueError, match="digits"):
        WhatsAppIntegrationUpdateSchema(catalog_id="catalog-name")

    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        with pytest.raises(ValueError, match="not found"):
            WhatsAppIntegrationService.update_integration(
                integration_id=integration["integration_id"],
                organization_id=test_setup["org_b"],
                data={"catalog_id": "123456789"},
            )


def test_whatsapp_interactive_buttons_boundaries_and_normalized_mapping():
    buttons = [
        {"type": "reply", "reply": {"id": f"choice_{index}", "title": f"Option {index}"}}
        for index in range(1, 4)
    ]
    buttons[0]["reply"]["id"] = "x" * 256
    buttons[0]["reply"]["title"] = "T" * 20
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": "H" * 60},
                "body": {"text": "B" * 1024},
                "footer": {"text": "F" * 60},
                "action": {"buttons": buttons},
            },
        },
    )

    mapped = payload["interactive"]
    assert len(mapped["action"]["buttons"]) == 3
    assert mapped["action"]["buttons"][0]["reply"]["id"] == "x" * 256
    assert len(mapped["action"]["buttons"][0]["reply"]["title"]) == 20
    assert len(mapped["body"]["text"]) == 1024
    assert len(mapped["footer"]["text"]) == 60


def test_whatsapp_interactive_button_ids_remain_reusable():
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Choose"},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": "shared_action", "title": "First"}},
                    {"type": "reply", "reply": {"id": "shared_action", "title": "Second"}},
                ]},
            },
        },
    )

    assert [button["reply"]["id"] for button in payload["interactive"]["action"]["buttons"]] == [
        "shared_action", "shared_action"
    ]


@pytest.mark.parametrize(
    ("interactive", "error"),
    [
        ({"type": "button", "body": {"text": "Pick"}, "action": {"buttons": []}}, "between 1 and 3"),
        (
            {"type": "button", "body": {"text": "Pick"}, "action": {"buttons": [
                {"type": "reply", "reply": {"id": "x", "title": "T" * 21}}
            ]}},
            "title.*1-20",
        ),
        (
            {"type": "button", "body": {"text": "Pick"}, "action": {"buttons": [
                {"type": "reply", "reply": {"id": " x", "title": "T"}}
            ]}},
            "leading or trailing whitespace",
        ),
        (
            {"type": "button", "body": {"text": "Pick"}, "action": {"buttons": [
                {"type": "reply", "reply": {"id": "x" * 257, "title": "T"}}
            ]}},
            "1-256 chars",
        ),
        (
            {"type": "button", "body": {"text": "Pick"}, "action": {"buttons": [
                {"type": "reply", "reply": {"id": "same", "title": "One"}},
                {"type": "reply", "reply": {"id": "other", "title": "One"}},
            ]}},
            "titles must be unique",
        ),
        (
            {"type": "button", "header": {"type": "image"}, "body": {"text": "Pick"},
             "action": {"buttons": [{"type": "reply", "reply": {"id": "x", "title": "T"}}]}},
            "requires matching content",
        ),
        (
            {"type": "button", "body": {"text": "B" * 1025}, "action": {"buttons": [
                {"type": "reply", "reply": {"id": "x", "title": "T"}}
            ]}},
            "exceeds maximum 1024",
        ),
    ],
)
def test_whatsapp_interactive_buttons_reject_invalid_payloads(interactive, error):
    with pytest.raises(ValueError, match=error):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={"type": "interactive", "interactive": interactive},
        )


def test_whatsapp_cta_url_button_maps_valid_absolute_url():
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "header": {"type": "text", "text": "Order online"},
                "body": {"text": "Continue to our secure order page"},
                "footer": {"text": "Example Shop"},
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": "Place order",
                        "url": "https://shop.example.test/orders?id=123",
                    },
                },
            },
        },
    )
    assert payload["interactive"]["action"] == {
        "name": "cta_url",
        "parameters": {
            "display_text": "Place order",
            "url": "https://shop.example.test/orders?id=123",
        },
    }


@pytest.mark.parametrize(
    ("action", "error"),
    [
        ({"name": "wrong", "parameters": {"display_text": "Open", "url": "https://example.test"}}, "must have 'name'"),
        ({"name": "cta_url", "parameters": None}, "object 'parameters'"),
        ({"name": "cta_url", "parameters": []}, "object 'parameters'"),
        ({"name": "cta_url", "parameters": {"display_text": "  ", "url": "https://example.test"}}, "display_text"),
        ({"name": "cta_url", "parameters": {"display_text": "T" * 21, "url": "https://example.test"}}, "display_text"),
        ({"name": "cta_url", "parameters": {"display_text": "Open", "url": "javascript:alert(1)"}}, "absolute HTTP or HTTPS URL"),
        ({"name": "cta_url", "parameters": {"display_text": "Open", "url": "https:///missing-host"}}, "absolute HTTP or HTTPS URL"),
        ({"name": "cta_url", "parameters": {"display_text": "Open", "url": "https://user:pass@example.test"}}, "absolute HTTP or HTTPS URL"),
        ({"name": "cta_url", "parameters": {"display_text": "Open", "url": "https://example.test:bad/path"}}, "absolute HTTP or HTTPS URL"),
    ],
)
def test_whatsapp_cta_url_rejects_invalid_action_parameters(action, error):
    with pytest.raises(ValueError, match=error):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={
                "type": "interactive",
                "interactive": {
                    "type": "cta_url", "body": {"text": "Open this page"}, "action": action,
                },
            },
        )


def test_whatsapp_interactive_list_boundaries_and_normalized_mapping():
    sections = [
        {
            "title": f"Section {section_index}",
            "rows": [{
                "id": f"row_{section_index}_0",
                "title": "R" * 24,
                "description": "D" * 72,
            }],
        }
        for section_index in range(10)
    ]
    sections[0]["rows"][0]["id"] = "i" * 200
    payload = WhatsAppPayloadValidator.validate_and_format(
        recipient="15551234567",
        data={
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "H" * 60},
                "body": {"text": "B" * 1024},
                "footer": {"text": "F" * 60},
                "action": {"button": "C" * 20, "sections": sections},
            },
        },
    )

    mapped = payload["interactive"]
    assert len(mapped["action"]["sections"]) == 10
    assert len(mapped["action"]["sections"][0]["rows"][0]["id"]) == 200
    assert len(mapped["action"]["sections"][0]["rows"][0]["title"]) == 24
    assert len(mapped["action"]["sections"][0]["rows"][0]["description"]) == 72
    assert len(mapped["action"]["button"]) == 20


@pytest.mark.parametrize(
    ("action", "header", "footer", "error"),
    [
        ({"button": "Menu", "sections": [{"rows": []}]}, None, None, "at least 1 item"),
        (
            {"button": "Menu", "sections": [{"rows": [{"id": f"r{i}", "title": "Row"} for i in range(11)]}]},
            None, None, "at most 10 items|maximum 10 total rows",
        ),
        (
            {"button": "Menu", "sections": [
                {"rows": [{"id": f"r{i}", "title": "Row"}]} for i in range(11)
            ]},
            None, None, "between 1 and 10 sections",
        ),
        (
            {"button": "Menu", "sections": [
                {"rows": [{"id": "duplicate", "title": "One"}]},
                {"rows": [{"id": "duplicate", "title": "Two"}]},
            ]},
            None, None, "IDs must be unique",
        ),
        (
            {"button": "M" * 21, "sections": [{"rows": [{"id": "r1", "title": "Row"}]}]},
            None, None, "1-20 characters",
        ),
        (
            {"button": "Menu", "sections": [{"rows": [{"id": "r1", "title": "R" * 25}]}]},
            None, None, "at most 24 characters",
        ),
        (
            {"button": "Menu", "sections": [{"rows": [{"id": "r1", "title": "Row"}]}]},
            {"type": "image", "image": {"link": "https://example.com/header.jpg"}}, None,
            "only a text header",
        ),
        (
            {"button": "Menu", "sections": [{"rows": [{"id": "r1", "title": "Row"}]}]},
            None, {"text": "F" * 61}, "maximum 60 characters",
        ),
    ],
)
def test_whatsapp_interactive_lists_reject_invalid_payloads(action, header, footer, error):
    interactive = {"type": "list", "body": {"text": "Browse"}, "action": action}
    if header is not None:
        interactive["header"] = header
    if footer is not None:
        interactive["footer"] = footer

    with pytest.raises(ValueError, match=error):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="15551234567",
            data={"type": "interactive", "interactive": interactive},
        )


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

        # Fail-closed check: Org A's module-fixture WhatsApp integration has no encrypted_access_token,
        # so multi-tenant dispatch resolution rejects it rather than silently using legacy provider_configs.
        with pytest.raises(ProviderResolutionError, match="has no configured access token"):
            AdapterRegistry.get_adapter(
                provider="meta",
                channel="whatsapp",
                organization_id=org_a
            )

        # Verify Org B does NOT have Org A's credentials
        with pytest.raises(ProviderResolutionError, match="No active WhatsApp integration found for this organization"):
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

        # Meta provider without credentials raises ProviderResolutionError, NEVER falls back to mock
        with pytest.raises(ProviderResolutionError, match="No active WhatsApp integration found for this organization"):
            AdapterRegistry.get_adapter(
                provider="meta",
                channel="whatsapp",
                organization_id=str(uuid.uuid4())
            )


def _get_test_whatsapp_integration(org_id):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository

    integrations = WhatsAppIntegrationRepository.find_active_by_organization(org_id)
    assert integrations
    return integrations[0]


@pytest.mark.parametrize("offset", [-0.000001, 0, 0.000001])
def test_whatsapp_customer_service_window_boundaries(app, test_setup, offset):
    """The exact 24-hour boundary is closed; only timestamps before it are open."""
    from datetime import datetime, timedelta, timezone

    opened_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    now = opened_at + timedelta(hours=24, seconds=offset)
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        app.mongo_db["inbound_messages"].insert_one({
            "_id": "wa-window-" + uuid.uuid4().hex,
            "organization_id": test_setup["org_a"],
            "integration_id": integration["integration_id"],
            "channel": "whatsapp",
            "phone_number_id": "10023456789",
            "from_phone": "15559876543",
            "provider_timestamp": opened_at.timestamp(),
        })
        result = MessageService.check_whatsapp_customer_service_window(
            recipient="+1 (555) 987-6543",
            organization_id=test_setup["org_a"],
            phone_number_id="10023456789",
            integration_id=integration["integration_id"],
            data={"type": "interactive", "interactive": {}},
            now=now,
        )
    assert result["allowed"] is (offset < 0)


def test_whatsapp_customer_service_window_missing_timestamp_and_template(app, test_setup):
    recipient = "1999" + f"{uuid.uuid4().int % 10**10:010d}"
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        result = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient, organization_id=test_setup["org_a"],
            phone_number_id="10023456789", integration_id=integration["integration_id"], data={"text": "hello"},
        )
        template_result = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient, organization_id=test_setup["org_a"],
            phone_number_id="10023456789", integration_id=integration["integration_id"],
            data={"type": "template", "template": {"name": "approved_template"}},
        )
    assert result["allowed"] is False
    assert "no valid inbound customer message timestamp" in result["reason"]
    assert template_result["allowed"] is True


def test_whatsapp_customer_service_window_is_tenant_and_integration_scoped(app, test_setup):
    from datetime import datetime, timezone

    recipient = "1998" + f"{uuid.uuid4().int % 10**10:010d}"
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        app.mongo_db["inbound_messages"].insert_one({
            "_id": "wa-window-tenant-" + uuid.uuid4().hex,
            "organization_id": test_setup["org_b"],
            "integration_id": "another-integration",
            "channel": "whatsapp",
            "phone_number_id": "10023456789",
            "from_phone": recipient,
            "provider_timestamp": datetime.now(timezone.utc).timestamp(),
        })
        result = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient, organization_id=test_setup["org_a"],
            phone_number_id="10023456789", integration_id=integration["integration_id"], data={"text": "hello"},
        )
    assert result["allowed"] is False


def test_whatsapp_customer_service_window_ignores_another_integration(app, test_setup):
    from datetime import datetime, timezone

    recipient = "1997" + f"{uuid.uuid4().int % 10**10:010d}"
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        app.mongo_db["inbound_messages"].insert_one({
            "_id": "wa-window-other-integration-" + uuid.uuid4().hex,
            "organization_id": test_setup["org_a"],
            "integration_id": "another-integration",
            "channel": "whatsapp",
            "phone_number_id": "10023456789",
            "from_phone": recipient,
            "provider_timestamp": datetime.now(timezone.utc).timestamp(),
        })
        result = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient,
            organization_id=test_setup["org_a"],
            phone_number_id="10023456789",
            integration_id=integration["integration_id"],
            data={"text": "hello"},
        )
    assert result["allowed"] is False


def test_whatsapp_dispatch_window_check_is_adjacent_to_provider_send(app, test_setup):
    from unittest.mock import patch
    from app.queue.tasks import process_message

    events = []
    integration = None
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        message = {
            "message_id": "dispatch-window-" + uuid.uuid4().hex,
            "organization_id": test_setup["org_a"],
            "channel": "whatsapp",
            "provider": "meta",
            "recipient": "15559876543",
            "data": {"type": "text", "text": "hello"},
            "integration_id": integration["integration_id"],
            "status": "QUEUED",
            "retry_count": 0,
        }

        class Adapter:
            def send(self, _message):
                events.append("provider_send")
                return {"success": True, "provider": "meta", "provider_message_id": "wamid.dispatch"}

        def make_adapter(**_kwargs):
            events.append("adapter_created")
            return Adapter()

        def check_window(**_kwargs):
            events.append("window_checked")
            return {"allowed": True}

        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_sent", return_value=True), \
             patch("app.modules.dead_letters.repository.DeadLetterRepository.find_by_message_id", return_value=None), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter", side_effect=make_adapter), \
             patch.object(MessageService, "check_whatsapp_customer_service_window", side_effect=check_window):
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is True
    assert events == ["adapter_created", "window_checked", "provider_send"]


def test_manual_retry_rejects_unknown_provider_acceptance(app, monkeypatch):
    from unittest.mock import patch

    message = {
        "message_id": "unknown-delivery-" + uuid.uuid4().hex,
        "organization_id": "org-unknown-delivery",
        "status": "FAILED",
        "last_error": "DELIVERY_OUTCOME_UNKNOWN: Meta may have accepted the request",
    }
    with app.app_context(), \
         patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
         patch("app.modules.messages.repository.MessageRepository.requeue_failed_message") as requeue:
        result = MessageService.retry_message(message["message_id"], message["organization_id"])
    assert result["success"] is False
    assert result["status_code"] == 409
    assert "reconcile delivery status" in result["message"]
    requeue.assert_not_called()


def test_delayed_whatsapp_dispatch_blocks_send_after_window_closes(app, test_setup):
    from unittest.mock import patch
    from app.queue.tasks import process_message

    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        message = {
            "message_id": "delayed-window-" + uuid.uuid4().hex,
            "organization_id": test_setup["org_a"],
            "channel": "whatsapp",
            "provider": "meta",
            "recipient": "15559876543",
            "data": {"type": "interactive", "interactive": {}},
            "integration_id": integration["integration_id"],
            "status": "QUEUED",
            "retry_count": 0,
        }
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_failed", return_value=True), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as make_adapter, \
             patch.object(MessageService, "check_whatsapp_customer_service_window", return_value={
                 "allowed": False,
                 "reason": "Cannot send a WhatsApp free-form message: the 24-hour customer service window has closed.",
             }):
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is False
    make_adapter.return_value.send.assert_not_called()


def test_legacy_org_scoped_template_dispatch_without_integration_is_preserved(app, test_setup):
    from unittest.mock import patch
    from app.queue.tasks import process_message

    org_id = test_setup["org_b"]
    message = {
        "message_id": "legacy-template-" + uuid.uuid4().hex,
        "organization_id": org_id,
        "channel": "whatsapp",
        "provider": "meta",
        "recipient": "15559876543",
        "data": {"type": "template", "template": {"name": "approved_template", "language": {"code": "en"}}},
        "status": "QUEUED",
        "retry_count": 0,
    }
    with app.app_context():
        assert not _get_org_whatsapp_integrations(org_id)
        ProviderConfigService.save_configuration("meta", {
            "access_token": "tenant-scoped-test-token",
            "phone_number_id": "10000000077",
        }, organization_id=org_id)
        adapter = MagicMock()
        adapter.send.return_value = {"success": True, "provider": "meta", "provider_message_id": "wamid.template"}
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_sent", return_value=True), \
             patch("app.modules.dead_letters.repository.DeadLetterRepository.find_by_message_id", return_value=None), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter", return_value=adapter):
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is True
    adapter.send.assert_called_once_with(message)


def test_legacy_template_does_not_use_global_env_credentials_without_tenant_config(app, monkeypatch):
    from unittest.mock import patch
    from app.queue.tasks import process_message

    organization_id = "org-no-wa-config-" + uuid.uuid4().hex
    message = {
        "message_id": "unscoped-template-" + uuid.uuid4().hex,
        "organization_id": organization_id,
        "channel": "whatsapp",
        "provider": "meta",
        "recipient": "15559876543",
        "data": {"type": "template", "template": {"name": "approved_template", "language": {"code": "en"}}},
        "status": "QUEUED",
        "retry_count": 0,
    }
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "global-test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "global-test-phone")
    with app.app_context():
        with patch("app.modules.messages.repository.MessageRepository.find_by_id", return_value=message), \
             patch("app.modules.messages.repository.MessageRepository.update_status", return_value=True), \
             patch("app.modules.messages.repository.MessageRepository.mark_failed", return_value=True), \
             patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as make_adapter:
            result = process_message.apply(args=[message["message_id"]]).result

    assert result["success"] is False
    make_adapter.assert_not_called()


def test_whatsapp_window_recheck_observes_new_inbound_timestamp(app, test_setup):
    from datetime import datetime, timedelta, timezone

    recipient = "1996" + f"{uuid.uuid4().int % 10**10:010d}"
    now = datetime.now(timezone.utc)
    with app.app_context():
        integration = _get_test_whatsapp_integration(test_setup["org_a"])
        inbound = app.mongo_db["inbound_messages"]
        record_id = "wa-window-retry-" + uuid.uuid4().hex
        inbound.insert_one({
            "_id": record_id,
            "organization_id": test_setup["org_a"],
            "integration_id": integration["integration_id"],
            "channel": "whatsapp",
            "phone_number_id": integration["phone_number_id"],
            "from_phone": recipient,
            "provider_timestamp": (now - timedelta(hours=25)).timestamp(),
        })
        first = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient, organization_id=test_setup["org_a"],
            phone_number_id=integration["phone_number_id"],
            integration_id=integration["integration_id"], data={"text": "hello"}, now=now,
        )
        inbound.update_one({"_id": record_id}, {"$set": {"provider_timestamp": now.timestamp()}})
        retry_check = MessageService.check_whatsapp_customer_service_window(
            recipient=recipient, organization_id=test_setup["org_a"],
            phone_number_id=integration["phone_number_id"],
            integration_id=integration["integration_id"], data={"text": "hello"}, now=now,
        )
    assert first["allowed"] is False
    assert retry_check["allowed"] is True


def _get_org_whatsapp_integrations(org_id):
    from app.modules.whatsapp.repository import WhatsAppIntegrationRepository

    return WhatsAppIntegrationRepository.find_all_by_organization(org_id, include_deleted=True)
