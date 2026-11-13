"""
SenderX Payload Encryption at Rest with Key Rotation Support
Provides authenticated field-level encryption for ingested payloads stored in MongoDB.
Uses MultiFernet (AES-128-CBC + HMAC-SHA256) backed by CREDENTIAL_ENCRYPTION_KEY
and optional CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS.
Fails closed if encryption keys are missing or corrupted.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from flask import current_app, has_app_context


class PayloadEncryptionError(Exception):
    """Raised when payload encryption or decryption fails."""
    pass


class PayloadEncryption:
    """Authenticated encryption helper supporting multi-key rotation and legacy migration."""

    @classmethod
    def _get_fernet_instances(cls) -> Tuple[Fernet, MultiFernet, str]:
        """
        Load primary encryption key and any previous rotation keys.
        Returns (primary_fernet, multi_fernet, active_key_version).
        """
        primary_key = None
        previous_keys_raw = None
        key_version = "v1"

        if has_app_context():
            primary_key = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY")
            previous_keys_raw = current_app.config.get("CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS")
            key_version = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY_VERSION", "v1")

        if not primary_key:
            primary_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        if not previous_keys_raw:
            previous_keys_raw = os.getenv("CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS", "")
        if not key_version or key_version == "v1":
            key_version = os.getenv("CREDENTIAL_ENCRYPTION_KEY_VERSION", "v1")

        if not primary_key:
            raise PayloadEncryptionError(
                "CREDENTIAL_ENCRYPTION_KEY is not configured. "
                "Production requires an authoritative encryption key for payloads at rest."
            )

        previous_keys: List[str] = []
        if isinstance(previous_keys_raw, list):
            previous_keys = [k.strip() for k in previous_keys_raw if k and str(k).strip()]
        elif isinstance(previous_keys_raw, str) and previous_keys_raw.strip():
            previous_keys = [k.strip() for k in previous_keys_raw.split(",") if k.strip()]

        try:
            primary_fernet = Fernet(primary_key.encode("utf-8") if isinstance(primary_key, str) else primary_key)
            all_fernets = [primary_fernet]
            for pk in previous_keys:
                all_fernets.append(Fernet(pk.encode("utf-8") if isinstance(pk, str) else pk))
            multi_fernet = MultiFernet(all_fernets)
            return primary_fernet, multi_fernet, str(key_version)
        except Exception as exc:
            raise PayloadEncryptionError(f"Invalid encryption key configuration: {exc}") from exc

    @classmethod
    def encrypt_dict(cls, data: Any, key_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Encrypt a JSON-serializable dictionary into an authenticated encrypted envelope
        using the primary (active) encryption key. Fails closed on error.
        """
        if data is None:
            return {}

        primary_fernet, _, default_version = cls._get_fernet_instances()
        version = key_version or default_version

        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            token = primary_fernet.encrypt(serialized).decode("ascii")
            return {
                "_encrypted": True,
                "algorithm": "Fernet/AES-128-CBC+HMAC-SHA256",
                "key_version": version,
                "ciphertext": token
            }
        except Exception as exc:
            raise PayloadEncryptionError(f"Failed to encrypt payload at rest: {exc}") from exc

    @classmethod
    def decrypt_dict(cls, envelope_or_dict: Any) -> Any:
        """
        Decrypt an encrypted envelope back into its original dictionary structure.
        Uses MultiFernet to transparently try primary and all previous rotation keys.
        Enforces ALLOW_PLAINTEXT_PAYLOAD_FALLBACK for legacy plaintext dictionaries.
        Fails closed if the ciphertext is corrupted or tampering is detected.
        """
        if not isinstance(envelope_or_dict, dict):
            return envelope_or_dict

        if not envelope_or_dict.get("_encrypted"):
            # Plaintext legacy record
            allow_fallback = True
            if has_app_context():
                allow_fallback = current_app.config.get("ALLOW_PLAINTEXT_PAYLOAD_FALLBACK", True)
            else:
                allow_fallback = os.getenv("ALLOW_PLAINTEXT_PAYLOAD_FALLBACK", "true").lower() == "true"

            if not allow_fallback:
                raise PayloadEncryptionError(
                    "Plaintext payload detected but ALLOW_PLAINTEXT_PAYLOAD_FALLBACK is disabled. "
                    "All payloads must be migrated and encrypted at rest."
                )
            return envelope_or_dict

        ciphertext = envelope_or_dict.get("ciphertext")
        if not ciphertext or not isinstance(ciphertext, str):
            raise PayloadEncryptionError("Invalid encrypted payload envelope: missing ciphertext")

        _, multi_fernet, _ = cls._get_fernet_instances()
        try:
            decrypted_bytes = multi_fernet.decrypt(ciphertext.encode("ascii"))
            return json.loads(decrypted_bytes.decode("utf-8"))
        except InvalidToken as exc:
            raise PayloadEncryptionError("Failed to decrypt payload: invalid token or corrupted ciphertext") from exc
        except Exception as exc:
            raise PayloadEncryptionError(f"Failed to decode decrypted payload JSON: {exc}") from exc

    @classmethod
    def reencrypt_envelope(cls, envelope: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Re-encrypt an existing encrypted envelope under the current primary key.
        Returns (new_envelope, was_rotated).
        """
        if not isinstance(envelope, dict) or not envelope.get("_encrypted"):
            return envelope, False

        _, _, current_version = cls._get_fernet_instances()
        current_envelope_version = envelope.get("key_version")

        # If already encrypted under current version, skip re-encryption
        if current_envelope_version == current_version:
            return envelope, False

        # Decrypt with multi_fernet and re-encrypt with primary key
        decrypted = cls.decrypt_dict(envelope)
        new_envelope = cls.encrypt_dict(decrypted, key_version=current_version)
        return new_envelope, True
