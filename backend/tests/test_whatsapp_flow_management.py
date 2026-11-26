"""Mocked tests for tenant-scoped WhatsApp Flow management and endpoint exchange."""

import hashlib
import hmac
import json
import threading

from pymongo.errors import DuplicateKeyError

from app.modules.whatsapp import flows as flow_module
from app.modules.whatsapp.flows import WhatsAppFlowService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.lock = threading.Lock()

    def find_one(self, query, projection=None):
        result = next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)
        if result is None:
            return None
        result = dict(result)
        if projection:
            for field, include in projection.items():
                if include == 0:
                    result.pop(field, None)
        return result

    def insert_one(self, doc):
        with self.lock:
            if any(d.get("_id") == doc.get("_id") for d in self.docs):
                raise DuplicateKeyError("duplicate _id")
            self.docs.append(dict(doc))

    def update_one(self, query, update):
        doc = next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)
        if doc:
            doc.update(update.get("$set", {}))

    def find(self, query, projection=None):
        return iter([self.find_one({**query, "flow_id": doc.get("flow_id")}, projection) for doc in self.docs if all(doc.get(k) == v for k, v in query.items())])

    def delete_one(self, query):
        from types import SimpleNamespace
        for index, doc in enumerate(self.docs):
            if all(doc.get(k) == v for k, v in query.items()):
                self.docs.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


def test_flow_create_update_publish_use_meta_graph_and_store_tenant_scope(monkeypatch):
    collection = FakeCollection()
    calls = []

    class FakeMeta:
        def request_graph(self, method, path, token, **kwargs):
            calls.append((method, path, token, kwargs))
            if path.endswith("/flows"):
                return {"id": "flow-123"}
            if path.endswith("/publish"):
                return {"success": True}
            return {"success": True}

    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: collection)
    monkeypatch.setattr(WhatsAppFlowService, "_integration", lambda org, integration: {"integration_id": integration, "waba_id": "waba-1"})
    monkeypatch.setattr(WhatsAppFlowService, "_credentials", lambda org, integration: (
        {"integration_id": integration, "waba_id": "waba-1"}, {"access_token": "private-token"}, FakeMeta()
    ))
    monkeypatch.setattr(WhatsAppFlowService, "_audit", lambda *args, **kwargs: None)
    doc = WhatsAppFlowService.create_flow("org-a", "int-a", {"name": "Booking", "categories": ["APPOINTMENT_BOOKING"], "flow_json": {"version": "7.3", "screens": [{"id": "START"}]}})
    assert doc["flow_id"] == "flow-123"
    assert collection.docs[0]["organization_id"] == "org-a"
    updated = WhatsAppFlowService.update_flow("org-a", "int-a", "flow-123", {"name": "Booking v2", "flow_json": {"version": "7.3", "screens": [{"id": "START"}]}})
    assert updated["name"] == "Booking v2"
    published = WhatsAppFlowService.publish_flow("org-a", "int-a", "flow-123")
    assert published["flow"]["status"] == "PUBLISHED"
    assert calls[0][1] == "waba-1/flows"
    assert any(path.endswith("/assets") for _, path, _, _ in calls)
    assert any(path.endswith("/publish") for _, path, _, _ in calls)


def test_flow_management_refuses_cross_organization_flow(monkeypatch):
    collection = FakeCollection([{"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a"}])
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: collection)
    monkeypatch.setattr(WhatsAppFlowService, "_integration", lambda org, int_id: {"integration_id": int_id})
    assert WhatsAppFlowService.get_flow("org-b", "int-a", "flow-a") is None


def test_flow_private_key_is_encrypted_before_integration_storage(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(WhatsAppFlowService, "_credentials", lambda org, integration: (
        {"integration_id": integration, "phone_number_id": "phone-a", "encrypted_flow_private_key": "old-cipher", "flow_key_version": "key-old", "flow_public_key_fingerprint": "old-fingerprint"},
        {"access_token": "mock-access-token"},
        type("Meta", (), {"request_graph": lambda self, *args, **kwargs: {"success": True}})(),
    ))
    captured = {}
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "update", lambda i, o, fields: captured.update(fields) or True)
    monkeypatch.setattr(WhatsAppFlowService, "_audit", lambda *args, **kwargs: None)
    result = WhatsAppFlowService.setup_encryption_key("org-a", "int-a")
    assert "BEGIN RSA PRIVATE KEY" not in captured["encrypted_flow_private_key"]
    assert "BEGIN PRIVATE KEY" not in captured["encrypted_flow_private_key"]
    assert captured["encrypted_flow_private_keys"][0]["ciphertext"] == "old-cipher"
    assert captured["encrypted_flow_private_keys"][0]["public_key_fingerprint"] == "old-fingerprint"
    decrypted = flow_module.WhatsAppEncryption.decrypt_secret(captured["encrypted_flow_private_key"])
    assert decrypted.startswith("-----BEGIN PRIVATE KEY-----")
    assert result["registered"] is True


def test_flow_key_serializer_omits_current_and_previous_ciphertext():
    from app.modules.whatsapp.models import serialize_integration
    value = serialize_integration({
        "integration_id": "int-a",
        "encrypted_flow_private_key": "current-ciphertext",
        "encrypted_flow_private_keys": [{"ciphertext": "previous-ciphertext"}],
    })
    assert "encrypted_flow_private_key" not in value
    assert "encrypted_flow_private_keys" not in value
    assert "current-ciphertext" not in str(value)
    assert "previous-ciphertext" not in str(value)


def test_flow_endpoint_signature_failure_stops_before_decryption(monkeypatch):
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a", "encrypted_flow_private_key": "cipher"})
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([{"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a", "endpoint_enabled": True}]))
    monkeypatch.setattr(flow_module.PlatformSettingsService, "get_meta_settings", lambda **k: {"meta_app_secret": "app-secret"})
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_secret", lambda value: (_ for _ in ()).throw(AssertionError("must not decrypt")))
    assert WhatsAppFlowService.exchange("int-a", "flow-a", b"{}", "sha256=wrong") == ("", 401)


def test_flow_endpoint_returns_encrypted_handler_response_without_leaking_plaintext(monkeypatch):
    secret = "app-secret"
    raw = json.dumps({"encrypted_flow_data": "ciphertext"}).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    integration = {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a", "encrypted_flow_private_key": "new-cipher", "encrypted_flow_private_keys": [{"ciphertext": "old-cipher"}]}
    flow_doc = {"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a", "endpoint_enabled": True, "endpoint_handlers": {"CONTACT:data_exchange": {"screen": "SUCCESS", "data": {"ok": True}}}}
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: integration)
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([flow_doc]))
    exchanges = FakeCollection()
    monkeypatch.setattr(WhatsAppFlowService, "_exchange_collection", lambda: exchanges)
    monkeypatch.setattr(flow_module.PlatformSettingsService, "get_meta_settings", lambda **k: {"meta_app_secret": secret})
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_secret", lambda value: f"private-key:{value}")
    attempted_keys = []
    def decrypt_with_rotation(key, body):
        attempted_keys.append(key)
        if key.endswith("new-cipher"):
            raise flow_module.WhatsAppEncryptionError("not the matching in-flight key")
        return {"action": "data_exchange", "screen": "CONTACT"}, b"a" * 16, b"b" * 16
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_flow_request", decrypt_with_rotation)
    encrypt_calls = []
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "encrypt_flow_response", lambda response, key, iv: encrypt_calls.append(response) or "encrypted-response")
    assert WhatsAppFlowService.exchange("int-a", "flow-a", raw, signature) == ("encrypted-response", 200)
    assert WhatsAppFlowService.exchange("int-a", "flow-a", raw, signature) == ("encrypted-response", 200)
    assert len(encrypt_calls) == 1
    assert exchanges.docs[0]["state"] == "COMPLETED"
    assert attempted_keys == ["private-key:new-cipher", "private-key:old-cipher"]


def test_flow_exchange_concurrent_duplicate_is_not_processed_twice(monkeypatch):
    secret = "app-secret"
    raw = b'{"encrypted_flow_data":"same-request"}'
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    integration = {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a", "encrypted_flow_private_key": "cipher"}
    flow_doc = {"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a", "endpoint_enabled": True, "endpoint_handlers": {"CONTACT:data_exchange": {"screen": "SUCCESS", "data": {"ok": True}}}}
    exchanges = FakeCollection()
    barrier = threading.Barrier(2)
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: integration)
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([flow_doc]))
    monkeypatch.setattr(WhatsAppFlowService, "_exchange_collection", lambda: exchanges)
    monkeypatch.setattr(flow_module.PlatformSettingsService, "get_meta_settings", lambda **k: {"meta_app_secret": secret})
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_secret", lambda value: "private-key")
    def decrypt(*args, **kwargs):
        barrier.wait(timeout=3)
        return {"action": "data_exchange", "screen": "CONTACT"}, b"a" * 16, b"b" * 16
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_flow_request", decrypt)
    encrypt_calls = []
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "encrypt_flow_response", lambda *args: encrypt_calls.append(1) or "response")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: WhatsAppFlowService.exchange("int-a", "flow-a", raw, signature), range(2)))
    assert all(status in (200, 503) for _, status in outcomes)
    assert 200 in [status for _, status in outcomes]
    assert len(encrypt_calls) == 1


def test_flow_completion_values_are_encrypted_tenant_scoped_and_deletable(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHATSAPP_FLOW_RESPONSE_RETENTION_DAYS", "1")
    records = FakeCollection()
    monkeypatch.setattr(WhatsAppFlowService, "_response_collection", lambda: records)
    def scoped_integration(org, integration):
        if org != "org-a" or integration != "int-a":
            raise ValueError("connected integration not found")
        return {"integration_id": integration}
    monkeypatch.setattr(WhatsAppFlowService, "_integration", scoped_integration)
    response = {"email": "sensitive@example.test", "answer": "private"}
    WhatsAppFlowService.store_completion("org-a", "int-a", "wamid-1", response)
    assert "sensitive@example.test" not in str(records.docs)
    result = WhatsAppFlowService.get_completion("org-a", "int-a", "wamid-1")
    assert result["response"] == response
    assert result["expires_at"] > result["created_at"]
    import pytest
    with pytest.raises(ValueError, match="connected integration"):
        WhatsAppFlowService.get_completion("org-b", "int-a", "wamid-1")
    assert WhatsAppFlowService.delete_completion("org-a", "int-a", "wamid-1") is True
    assert records.docs == []


def test_optional_meta_flow_token_signature_is_validated(monkeypatch):
    secret = "app-secret"
    raw = b'{"encrypted_flow_data":"ciphertext"}'
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a", "encrypted_flow_private_key": "cipher"})
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([{"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a", "endpoint_enabled": True}]))
    monkeypatch.setattr(WhatsAppFlowService, "_exchange_collection", lambda: FakeCollection())
    monkeypatch.setattr(flow_module.PlatformSettingsService, "get_meta_settings", lambda **k: {"meta_app_secret": secret})
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_secret", lambda value: "private-key")
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_flow_request", lambda key, body: ({"action": "INIT", "flow_token_signature": "invalid"}, b"a" * 16, b"b" * 16))
    assert WhatsAppFlowService.exchange("int-a", "flow-a", raw, signature) == ("", 401)


def test_flow_decryption_errors_return_meta_retry_status_without_details(monkeypatch):
    secret = "app-secret"
    raw = b'{"encrypted_flow_data":"ciphertext"}'
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a", "encrypted_flow_private_key": "cipher"})
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([{"organization_id": "org-a", "integration_id": "int-a", "flow_id": "flow-a", "endpoint_enabled": True}]))
    monkeypatch.setattr(WhatsAppFlowService, "_exchange_collection", lambda: FakeCollection())
    monkeypatch.setattr(flow_module.PlatformSettingsService, "get_meta_settings", lambda **k: {"meta_app_secret": secret})
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_secret", lambda value: "private-key")
    monkeypatch.setattr(flow_module.WhatsAppEncryption, "decrypt_flow_request", lambda *a, **k: (_ for _ in ()).throw(flow_module.WhatsAppEncryptionError("secret plaintext")))
    body, status = WhatsAppFlowService.exchange("int-a", "flow-a", raw, signature)
    assert body == ""
    assert status == 421


def test_flow_endpoint_does_not_match_flow_from_other_tenant(monkeypatch):
    monkeypatch.setattr(flow_module.WhatsAppIntegrationRepository, "find_by_id", lambda *a, **k: {"status": "CONNECTED", "organization_id": "org-a", "integration_id": "int-a"})
    monkeypatch.setattr(WhatsAppFlowService, "_collection", lambda: FakeCollection([{"organization_id": "org-b", "integration_id": "int-b", "flow_id": "flow-a", "endpoint_enabled": True}]))
    assert WhatsAppFlowService.exchange("int-a", "flow-a", b"{}", "sha256=anything") == ("", 404)


def test_flow_endpoint_http_contract_returns_ciphertext_as_plaintext(client, monkeypatch):
    seen = {}

    def exchange(integration_id, flow_id, raw_body, signature):
        seen.update({"integration_id": integration_id, "flow_id": flow_id, "raw_body": raw_body, "signature": signature})
        return "base64-ciphertext", 200

    monkeypatch.setattr(WhatsAppFlowService, "exchange", exchange)
    response = client.post(
        "/api/v1/whatsapp/flows/int-a/flow-a/data",
        data=b'{"encrypted_flow_data":"..."}',
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=abc"},
    )
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "base64-ciphertext"
    assert response.mimetype == "text/plain"
    assert seen["integration_id"] == "int-a"
    assert seen["signature"] == "sha256=abc"


def test_handler_configuration_requires_explicit_screen_and_data():
    import pytest
    with pytest.raises(ValueError, match="screen and data"):
        WhatsAppFlowService._validate_handlers({"data_exchange": {"screen": "NEXT"}})
