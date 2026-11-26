"""
SenderX WhatsApp Credential Encryption Service
Provides authenticated AES-128-CBC + HMAC-SHA256 (MultiFernet) field-level encryption
for organization-specific WhatsApp Cloud API access tokens and centralized platform secrets.
Fails closed if encryption keys are missing, invalid, or ciphertext has been tampered with.
"""

import os
import base64
import json
from typing import List, Optional, Tuple
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app, has_app_context


class WhatsAppEncryptionError(Exception):
    """Raised when WhatsApp token encryption or decryption fails."""
    pass


class WhatsAppEncryption:
    """Authenticated encryption helper supporting multi-key rotation for WhatsApp credentials."""

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
            raise WhatsAppEncryptionError(
                "CREDENTIAL_ENCRYPTION_KEY is not configured. "
                "Production requires an authoritative encryption key for WhatsApp credentials at rest."
            )

        previous_keys: List[str] = []
        if isinstance(previous_keys_raw, list):
            previous_keys = [k.strip() for k in previous_keys_raw if k and str(k).strip()]
        elif isinstance(previous_keys_raw, str) and previous_keys_raw.strip():
            previous_keys = [k.strip() for k in previous_keys_raw.split(",") if k.strip()]

        try:
            primary_bytes = primary_key.encode("utf-8") if isinstance(primary_key, str) else primary_key
            primary_fernet = Fernet(primary_bytes)
            all_fernets = [primary_fernet]
            for pk in previous_keys:
                pk_bytes = pk.encode("utf-8") if isinstance(pk, str) else pk
                all_fernets.append(Fernet(pk_bytes))
            multi_fernet = MultiFernet(all_fernets)
            return primary_fernet, multi_fernet, str(key_version)
        except Exception as exc:
            raise WhatsAppEncryptionError(f"Invalid encryption key configuration: {exc}") from exc

    @classmethod
    def encrypt_token(cls, raw_token: str, key_version: Optional[str] = None) -> Tuple[str, str]:
        """
        Encrypt a raw access token string using the primary encryption key.
        Returns (ciphertext, key_version). Fails closed on error.
        """
        if not raw_token or not isinstance(raw_token, str) or not raw_token.strip():
            raise WhatsAppEncryptionError("Access token must be a non-empty string")

        primary_fernet, _, default_version = cls._get_fernet_instances()
        version = key_version or default_version

        try:
            token_bytes = raw_token.strip().encode("utf-8")
            ciphertext = primary_fernet.encrypt(token_bytes).decode("ascii")
            return ciphertext, version
        except Exception as exc:
            raise WhatsAppEncryptionError(f"Failed to encrypt WhatsApp token: {exc}") from exc

    @classmethod
    def decrypt_token(cls, ciphertext: str) -> str:
        """
        Decrypt an encrypted token using MultiFernet (trying primary and rotation keys).
        Fails closed if the ciphertext is corrupted, tampered with, or cannot be decrypted.
        """
        if not ciphertext or not isinstance(ciphertext, str) or not ciphertext.strip():
            raise WhatsAppEncryptionError("Ciphertext must be a non-empty string")

        _, multi_fernet, _ = cls._get_fernet_instances()

        try:
            token_bytes = ciphertext.strip().encode("ascii")
            decrypted = multi_fernet.decrypt(token_bytes).decode("utf-8")
            return decrypted
        except InvalidToken as exc:
            raise WhatsAppEncryptionError(
                "WhatsApp access token decryption failed: invalid or tampered ciphertext"
            ) from exc
        except Exception as exc:
            raise WhatsAppEncryptionError(f"WhatsApp access token decryption failed: {exc}") from exc

    @classmethod
    def encrypt_secret(cls, raw_secret: str) -> Tuple[str, str]:
        """Encrypt an arbitrary integration secret using the configured Fernet key ring."""
        return cls.encrypt_token(raw_secret)

    @classmethod
    def decrypt_secret(cls, ciphertext: str) -> str:
        """Decrypt an arbitrary integration secret using the configured Fernet key ring."""
        return cls.decrypt_token(ciphertext)

    @classmethod
    def mask_token(cls, token: Optional[str]) -> str:
        """
        Produce a safe, redacted representation of a token for debugging.
        NEVER outputs the full token.
        """
        if not token or not isinstance(token, str):
            return "[NOT_CONFIGURED]"
        cleaned = token.strip()
        if len(cleaned) <= 12:
            return "******"
        return f"{cleaned[:4]}...{cleaned[-4:]}"

    @staticmethod
    def generate_flow_key_pair() -> Tuple[str, str]:
        """Create an RSA-2048 Flow key pair; callers must encrypt the private PEM at rest."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        return private_pem, public_pem

    @staticmethod
    def decrypt_flow_request(private_key_pem: str, payload: dict) -> Tuple[dict, bytes, bytes]:
        """Decrypt a Meta Flow data-exchange request without logging cleartext values."""
        if not isinstance(payload, dict):
            raise WhatsAppEncryptionError("Invalid WhatsApp Flow encrypted request")
        try:
            encrypted_data = base64.b64decode(payload["encrypted_flow_data"], validate=True)
            encrypted_key = base64.b64decode(payload["encrypted_aes_key"], validate=True)
            iv = base64.b64decode(payload["initial_vector"], validate=True)
            if len(iv) != 16 or len(encrypted_data) < 17:
                raise ValueError("Invalid encrypted payload size")
            private_key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
            aes_key = private_key.decrypt(
                encrypted_key,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
            )
            if len(aes_key) != 16:
                raise ValueError("Invalid AES key size")
            clear = AESGCM(aes_key).decrypt(iv, encrypted_data, None)
            decoded = json.loads(clear.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("Flow request must be an object")
            return decoded, aes_key, iv
        except WhatsAppEncryptionError:
            raise
        except Exception as exc:
            raise WhatsAppEncryptionError("WhatsApp Flow request decryption failed") from exc

    @staticmethod
    def encrypt_flow_response(response: dict, aes_key: bytes, iv: bytes) -> str:
        """Encrypt a Meta Flow endpoint response using the inverted request IV."""
        if not isinstance(response, dict) or len(aes_key) != 16 or len(iv) != 16:
            raise WhatsAppEncryptionError("Invalid WhatsApp Flow response encryption parameters")
        try:
            flipped_iv = bytes(byte ^ 0xFF for byte in iv)
            encrypted = AESGCM(aes_key).encrypt(flipped_iv, json.dumps(response, separators=(",", ":")).encode("utf-8"), None)
            return base64.b64encode(encrypted).decode("ascii")
        except Exception as exc:
            raise WhatsAppEncryptionError("WhatsApp Flow response encryption failed") from exc
