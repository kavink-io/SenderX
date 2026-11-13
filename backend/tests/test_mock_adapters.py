"""
SenderX Multi-Channel Mock Adapters Test Suite
Validates:
- MockEmailAdapter, MockSMSAdapter, MockWhatsAppAdapter, MockTelegramAdapter
- Required fields and recipient validation per channel
- Response structures (status, provider, channel, provider_message_id, timestamp)
- All 4 scenarios: success, permanent_failure, temporary_failure, temporary_then_success
- AdapterRegistry channel-based routing and unsupported combinations
- Celery worker integration across all 4 channels
"""

import uuid
import pytest

from app import create_app
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.email.mock_adapter import MockEmailAdapter
from app.adapters.sms.mock_adapter import MockSMSAdapter
from app.adapters.whatsapp.mock_adapter import MockWhatsAppAdapter
from app.adapters.telegram.mock_adapter import MockTelegramAdapter
from app.adapters.base_adapter import ProviderError
from app.engine.retry_manager import RetryManager
from app.modules.messages.repository import MessageRepository
from app.queue.tasks import process_message


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


# ======================================================
# 1. ADAPTER REGISTRY ROUTING TESTS
# ======================================================

def test_adapter_registry_channel_routing():
    """Verify AdapterRegistry routes each channel to the appropriate mock adapter."""
    # Explicit channels
    email_adapter = AdapterRegistry.get_adapter("mock", channel="email")
    assert isinstance(email_adapter, MockEmailAdapter)

    sms_adapter = AdapterRegistry.get_adapter("mock", channel="sms")
    assert isinstance(sms_adapter, MockSMSAdapter)

    wa_adapter = AdapterRegistry.get_adapter("mock", channel="whatsapp")
    assert isinstance(wa_adapter, MockWhatsAppAdapter)

    tg_adapter = AdapterRegistry.get_adapter("mock", channel="telegram")
    assert isinstance(tg_adapter, MockTelegramAdapter)

    # Backward compatibility: channel=None defaults to email
    default_adapter = AdapterRegistry.get_adapter("mock")
    assert isinstance(default_adapter, MockEmailAdapter)


def test_adapter_registry_unsupported_combinations():
    """Verify unsupported channel or provider combinations raise descriptive errors."""
    # Unsupported channel for mock
    with pytest.raises(ValueError) as exc:
        AdapterRegistry.get_adapter("mock", channel="fax")
    assert "unsupported channel 'fax'" in str(exc.value).lower()

    # Unsupported channel for SendGrid (only supports email)
    with pytest.raises(ValueError) as exc:
        AdapterRegistry.get_adapter("sendgrid", channel="sms")
    assert "only supports 'email'" in str(exc.value).lower()

    # Unsupported provider
    with pytest.raises(ValueError) as exc:
        AdapterRegistry.get_adapter("carrier_pigeon", channel="email")
    assert "unsupported provider" in str(exc.value).lower()


# ======================================================
# 2. EMAIL MOCK ADAPTER TESTS
# ======================================================

def test_mock_email_adapter():
    adapter = MockEmailAdapter()

    # Success scenario
    msg = {
        "recipient": "kavin@senderx.io",
        "data": {"subject": "Email Subject", "message": "Email Body", "mock_scenario": "success"},
        "retry_count": 0
    }
    res = adapter.send(msg)
    assert res["success"] is True
    assert res["status"] == "SENT"
    assert res["channel"] == "email"
    assert res["provider"] == "mock"
    assert res["provider_message_id"].startswith("mock-email-")
    assert "timestamp" in res

    # Validation errors
    with pytest.raises(ValueError, match="Invalid email recipient"):
        adapter.validate({"recipient": "invalid_email", "data": {"subject": "Hi", "message": "Hi"}})

    with pytest.raises(ValueError, match="Email subject is required"):
        adapter.validate({"recipient": "test@test.io", "data": {"message": "Hi"}})

    with pytest.raises(ValueError, match="Email content is required"):
        adapter.validate({"recipient": "test@test.io", "data": {"subject": "Hi"}})

    # Permanent failure
    msg_perm = {
        "recipient": "kavin@senderx.io",
        "data": {"subject": "S", "message": "M", "mock_scenario": "permanent_failure"}
    }
    with pytest.raises(ProviderError) as exc_perm:
        adapter.send(msg_perm)
    assert RetryManager.is_retryable_error(exc_perm.value) is False

    # Temporary failure
    msg_temp = {
        "recipient": "kavin@senderx.io",
        "data": {"subject": "S", "message": "M", "mock_scenario": "temporary_failure"}
    }
    with pytest.raises(ProviderError) as exc_temp:
        adapter.send(msg_temp)
    assert RetryManager.is_retryable_error(exc_temp.value) is True

    # Temporary then success: fails at retry_count=0,1; succeeds at retry_count=2
    msg_tts_0 = {
        "recipient": "kavin@senderx.io",
        "data": {"subject": "S", "message": "M", "mock_scenario": "temporary_then_success"},
        "retry_count": 1
    }
    with pytest.raises(ProviderError) as exc_tts:
        adapter.send(msg_tts_0)
    assert RetryManager.is_retryable_error(exc_tts.value) is True

    msg_tts_2 = {
        "recipient": "kavin@senderx.io",
        "data": {"subject": "S", "message": "M", "mock_scenario": "temporary_then_success"},
        "retry_count": 2
    }
    res_tts = adapter.send(msg_tts_2)
    assert res_tts["success"] is True


# ======================================================
# 3. SMS MOCK ADAPTER TESTS
# ======================================================

def test_mock_sms_adapter():
    adapter = MockSMSAdapter()

    # Success scenario
    msg = {
        "recipient": "+14155552671",
        "data": {"text": "Your verification code is 482910", "mock_scenario": "success"},
        "retry_count": 0
    }
    res = adapter.send(msg)
    assert res["success"] is True
    assert res["status"] == "SENT"
    assert res["channel"] == "sms"
    assert res["provider"] == "mock"
    assert res["provider_message_id"].startswith("mock-sms-")
    assert "timestamp" in res

    # Format message preserves arbitrary data
    formatted = adapter.format_message({
        "recipient": "+14155552671",
        "data": {"text": "Hello", "sender_id": "SenderX", "custom_id": 999}
    })
    assert formatted["to_phone"] == "+14155552671"
    assert formatted["text"] == "Hello"
    assert formatted["custom_id"] == 999

    # Validation errors
    with pytest.raises(ValueError, match="Invalid SMS recipient"):
        adapter.validate({"recipient": "not_a_phone_number", "data": {"text": "Code"}})

    with pytest.raises(ValueError, match="SMS text message content is required"):
        adapter.validate({"recipient": "+14155552671", "data": {}})

    # Permanent failure
    msg_perm = {"recipient": "+14155552671", "data": {"text": "Code", "mock_scenario": "permanent_failure"}}
    with pytest.raises(ProviderError) as exc_perm:
        adapter.send(msg_perm)
    assert RetryManager.is_retryable_error(exc_perm.value) is False

    # Temporary failure
    msg_temp = {"recipient": "+14155552671", "data": {"text": "Code", "mock_scenario": "temporary_failure"}}
    with pytest.raises(ProviderError) as exc_temp:
        adapter.send(msg_temp)
    assert RetryManager.is_retryable_error(exc_temp.value) is True

    # Temporary then success
    msg_tts_0 = {"recipient": "+14155552671", "data": {"text": "Code", "mock_scenario": "temporary_then_success"}, "retry_count": 0}
    with pytest.raises(ProviderError):
        adapter.send(msg_tts_0)

    msg_tts_2 = {"recipient": "+14155552671", "data": {"text": "Code", "mock_scenario": "temporary_then_success"}, "retry_count": 2}
    assert adapter.send(msg_tts_2)["success"] is True


# ======================================================
# 4. WHATSAPP MOCK ADAPTER TESTS
# ======================================================

def test_mock_whatsapp_adapter():
    adapter = MockWhatsAppAdapter()

    # Success scenario with standard phone
    msg1 = {
        "recipient": "+919876543210",
        "data": {"text": "Hello via WhatsApp!", "mock_scenario": "success"},
        "retry_count": 0
    }
    res1 = adapter.send(msg1)
    assert res1["success"] is True
    assert res1["channel"] == "whatsapp"
    assert res1["provider_message_id"].startswith("mock-wa-")

    # Success scenario with whatsapp: URI and media
    msg2 = {
        "recipient": "whatsapp:+919876543210",
        "data": {
            "template_name": "order_update",
            "media_url": "https://cdn.example.com/receipt.pdf",
            "mock_scenario": "success"
        },
        "retry_count": 0
    }
    res2 = adapter.send(msg2)
    assert res2["success"] is True

    # Validation errors
    with pytest.raises(ValueError, match="Invalid WhatsApp recipient"):
        adapter.validate({"recipient": "invalid_whatsapp_handle", "data": {"text": "Hi"}})

    with pytest.raises(ValueError, match="requires text, template, or media"):
        adapter.validate({"recipient": "+919876543210", "data": {}})

    # Permanent & temporary failure scenarios
    with pytest.raises(ProviderError) as exc_p:
        adapter.send({"recipient": "+919876543210", "data": {"text": "T", "mock_scenario": "permanent_failure"}})
    assert RetryManager.is_retryable_error(exc_p.value) is False

    with pytest.raises(ProviderError) as exc_t:
        adapter.send({"recipient": "+919876543210", "data": {"text": "T", "mock_scenario": "temporary_failure"}})
    assert RetryManager.is_retryable_error(exc_t.value) is True


# ======================================================
# 5. TELEGRAM MOCK ADAPTER TESTS
# ======================================================

def test_mock_telegram_adapter():
    adapter = MockTelegramAdapter()

    # Success scenario with numeric chat_id
    msg1 = {
        "recipient": "-100192837465",
        "data": {"text": "Alert: deployment successful", "mock_scenario": "success"},
        "retry_count": 0
    }
    res1 = adapter.send(msg1)
    assert res1["success"] is True
    assert res1["channel"] == "telegram"
    assert res1["provider_message_id"].startswith("mock-tg-")

    # Success scenario with username
    msg2 = {
        "recipient": "@senderx_bot",
        "data": {"caption": "Weekly metrics", "photo": "https://cdn.example.com/chart.png"},
        "retry_count": 0
    }
    res2 = adapter.send(msg2)
    assert res2["success"] is True

    # Validation errors
    with pytest.raises(ValueError, match="Invalid Telegram recipient"):
        adapter.validate({"recipient": "invalid handle without @ or numbers", "data": {"text": "Hi"}})

    with pytest.raises(ValueError, match="Telegram message content"):
        adapter.validate({"recipient": "@valid_bot", "data": {}})

    # Permanent & temporary failure scenarios
    with pytest.raises(ProviderError) as exc_p:
        adapter.send({"recipient": "@valid_bot", "data": {"text": "T", "mock_scenario": "permanent_failure"}})
    assert RetryManager.is_retryable_error(exc_p.value) is False

    with pytest.raises(ProviderError) as exc_t:
        adapter.send({"recipient": "@valid_bot", "data": {"text": "T", "mock_scenario": "temporary_failure"}})
    assert RetryManager.is_retryable_error(exc_t.value) is True


# ======================================================
# 6. CELERY WORKER MULTI-CHANNEL INTEGRATION TESTS
# ======================================================

def test_worker_processing_across_all_four_channels(app):
    """Verify Celery task processes all 4 channels (email, sms, whatsapp, telegram) to SENT."""
    with app.app_context():
        org_id = f"org-channels-{uuid.uuid4().hex[:6]}"
        test_messages = [
            ("email", "test@senderx.io", {"subject": "Test", "message": "Email test"}),
            ("sms", "+15551234567", {"text": "SMS test"}),
            ("whatsapp", "+15557654321", {"text": "WhatsApp test"}),
            ("telegram", "@senderx_channel", {"text": "Telegram test"})
        ]

        created_ids = []

        try:
            for channel, recipient, data in test_messages:
                msg_id = f"test-{channel}-{uuid.uuid4().hex[:6]}"
                created_ids.append(msg_id)

                data["mock_scenario"] = "success"
                MessageRepository.save({
                    "message_id": msg_id,
                    "organization_id": org_id,
                    "channel": channel,
                    "provider": "mock",
                    "recipient": recipient,
                    "data": data,
                    "status": "QUEUED",
                    "retry_count": 0
                })

                # Process using Celery task directly
                async_res = process_message.apply(args=[msg_id])
                result = async_res.result

                assert result["success"] is True
                assert result["status"] == "SENT"
                assert result["provider"] == "mock"
                assert result["provider_message_id"] is not None

                # Verify message in database
                saved = MessageRepository.find_by_id(msg_id, organization_id=org_id)
                assert saved["status"] == "SENT"
                assert saved["provider_message_id"] == result["provider_message_id"]

        finally:
            for msg_id in created_ids:
                MessageRepository._collection().delete_one({"message_id": msg_id})
