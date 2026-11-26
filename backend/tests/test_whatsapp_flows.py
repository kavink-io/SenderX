"""Focused unit coverage for WhatsApp Flow mapping, webhook normalization and crypto."""

import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.adapters.whatsapp.models import WhatsAppPayloadValidator
from app.modules.messages.service import MessageService
from app.modules.whatsapp.encryption import WhatsAppEncryption, WhatsAppEncryptionError


def test_flow_message_maps_to_meta_interactive_payload():
    mapped = WhatsAppPayloadValidator.validate_and_format(
        recipient="+14155552671",
        data={
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "body": {"text": "Complete this form"},
                "action": {
                    "name": "flow",
                    "parameters": {
                        "flow_message_version": "3",
                        "flow_id": "1234567890",
                        "flow_cta": "Continue",
                        "flow_token": "opaque-session-token",
                        "flow_action": "navigate",
                        "flow_action_payload": {"screen": "CONTACT", "data": {"source": "senderx"}},
                    },
                },
            },
        },
    )
    assert mapped["type"] == "interactive"
    assert mapped["interactive"]["type"] == "flow"
    assert mapped["interactive"]["action"]["parameters"]["flow_action_payload"]["screen"] == "CONTACT"


def test_approved_flow_template_component_maps_action_parameters():
    mapped = WhatsAppPayloadValidator.validate_and_format(
        recipient="+14155552671",
        data={
            "type": "template",
            "template": {
                "name": "approved_flow_template",
                "language": "en_US",
                "components": [{
                    "type": "button",
                    "sub_type": "flow",
                    "index": 0,
                    "parameters": [{"type": "action", "action": {"flow_token": "opaque-session", "flow_action_data": {"source": "api"}}}],
                }],
            },
        },
    )
    parameter = mapped["template"]["components"][0]["parameters"][0]
    assert parameter["type"] == "action"
    assert parameter["action"]["flow_token"] == "opaque-session"


@pytest.mark.parametrize(
    "parameters",
    [
        {"flow_message_version": "2", "flow_id": "1", "flow_cta": "Go"},
        {"flow_message_version": "3", "flow_cta": "Go"},
        {"flow_message_version": "3", "flow_id": "1", "flow_name": "named", "flow_cta": "Go"},
        {"flow_message_version": "3", "flow_id": "1", "flow_cta": ""},
        {"flow_message_version": "3", "flow_id": "1", "flow_cta": "Continue", "flow_action": "navigate", "flow_action_payload": {"data": {}}},
    ],
)
def test_flow_mapping_rejects_invalid_parameters(parameters):
    with pytest.raises(ValueError):
        WhatsAppPayloadValidator.validate_and_format(
            recipient="+14155552671",
            data={"type": "interactive", "interactive": {"type": "flow", "body": {"text": "Open"}, "action": {"name": "flow", "parameters": parameters}}},
        )


def test_flow_completion_webhook_normalizes_json_and_keeps_event_scope():
    event = MessageService._normalize_whatsapp_interactive_event(
        message={
            "id": "wamid.flow-complete",
            "from": "14155552671",
            "timestamp": "1700000000",
            "type": "interactive",
            "interactive": {"type": "nfm_reply", "nfm_reply": {"name": "flow", "body": "Submitted", "response_json": '{"screen":"SUCCESS","email":"person@example.test"}'}},
        },
        organization_id="org-a",
        integration_id="integration-a",
        phone_number_id="phone-a",
    )
    assert event["event_type"] == "whatsapp.flow.completed"
    assert event["organization_id"] == "org-a"
    assert event["integration_id"] == "integration-a"
    assert event["flow_response"] == {"screen": "SUCCESS", "email": "person@example.test"}


def test_flow_completion_malformed_response_is_unknown_not_parsed():
    event = MessageService._normalize_whatsapp_interactive_event(
        message={"id": "wamid.bad-flow", "type": "interactive", "interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": "not-json"}}},
        organization_id="org-a",
        integration_id="integration-a",
        phone_number_id="phone-a",
    )
    assert event["event_type"] == "whatsapp.interactive.unknown"


def test_flow_crypto_round_trip_matches_meta_aes_gcm_iv_scheme():
    private_pem, public_pem = WhatsAppEncryption.generate_flow_key_pair()
    from cryptography.hazmat.primitives import serialization

    public_key = serialization.load_pem_public_key(public_pem.encode("ascii"))
    aes_key = AESGCM.generate_key(bit_length=128)
    iv = b"0123456789abcdef"
    request_data = {"version": "3.0", "action": "ping"}
    encrypted_request = AESGCM(aes_key).encrypt(iv, json.dumps(request_data).encode(), None)
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    decrypted, key, request_iv = WhatsAppEncryption.decrypt_flow_request(
        private_pem,
        {
            "encrypted_flow_data": base64.b64encode(encrypted_request).decode(),
            "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode(),
            "initial_vector": base64.b64encode(iv).decode(),
        },
    )
    assert decrypted == request_data
    encrypted_response = base64.b64decode(WhatsAppEncryption.encrypt_flow_response({"data": {"status": "active"}}, key, request_iv))
    response_iv = bytes(byte ^ 0xFF for byte in iv)
    assert json.loads(AESGCM(aes_key).decrypt(response_iv, encrypted_response, None)) == {"data": {"status": "active"}}


def test_flow_crypto_rejects_malformed_payload_without_exposing_contents():
    private_pem, _ = WhatsAppEncryption.generate_flow_key_pair()
    with pytest.raises(WhatsAppEncryptionError, match="decryption failed"):
        WhatsAppEncryption.decrypt_flow_request(private_pem, {"encrypted_flow_data": "bad", "encrypted_aes_key": "bad", "initial_vector": "bad"})


def test_flow_crypto_rejects_invalid_private_key():
    from base64 import b64encode
    payload = {"encrypted_flow_data": b64encode(b"x" * 32).decode(), "encrypted_aes_key": b64encode(b"x" * 256).decode(), "initial_vector": b64encode(b"x" * 16).decode()}
    with pytest.raises(WhatsAppEncryptionError, match="decryption failed"):
        WhatsAppEncryption.decrypt_flow_request("not a PEM private key", payload)
