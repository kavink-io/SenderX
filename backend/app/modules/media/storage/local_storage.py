"""
SenderX Local Filesystem Storage Backend
Used for development, local testing, and offline environments.
Provides strict path traversal protection and secure directory isolation.
"""

import hmac
import hashlib
import os
import shutil
import time
from typing import Any, BinaryIO, Dict, List, Optional, Union

from app.modules.media.storage.base_storage import (
    BaseStorage,
    StorageNotFoundError,
    StorageOperationError,
    StorageSecurityError,
)


class LocalStorage(BaseStorage):
    """
    Local filesystem storage backend with tenant directory isolation
    and strict path traversal prevention.
    """

    def __init__(self, base_dir: str, signing_secret: Optional[str] = None):
        if not base_dir:
            raise ValueError("LocalStorage requires 'base_dir'")
        self.base_dir = os.path.abspath(base_dir)
        self.signing_secret = signing_secret or "senderx-media-signing-secret"
        os.makedirs(self.base_dir, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "local"

    def _resolve_safe_path(self, storage_key: str, organization_id: Optional[str] = None) -> str:
        """
        Resolve storage_key against base_dir and strictly ensure it cannot escape base_dir.
        Guards against directory traversal (../, ..\\, absolute paths, null bytes)
        and cross-tenant boundary escape.
        """
        if not storage_key or not isinstance(storage_key, str):
            raise StorageSecurityError("Storage key must be a non-empty string")

        if "\x00" in storage_key:
            raise StorageSecurityError("Storage key contains invalid null bytes")

        # Strip leading slashes to prevent root-relative path escape
        normalized_key = storage_key.strip().replace("\\", "/").lstrip("/")
        
        # Check for explicit traversal components
        parts = normalized_key.split("/")
        if any(part in ("..", ".") for part in parts):
            raise StorageSecurityError(f"Path traversal detected in key: {storage_key}")

        if organization_id:
            expected_prefix = f"orgs/{organization_id}/"
            if not normalized_key.startswith(expected_prefix):
                raise StorageSecurityError(
                    f"Cross-tenant storage access violation: storage key does not belong to organization '{organization_id}'"
                )

        full_path = os.path.abspath(os.path.join(self.base_dir, *parts))
        base_abs = os.path.abspath(self.base_dir)

        if not (full_path == base_abs or full_path.startswith(base_abs + os.sep)):
            raise StorageSecurityError(f"Path traversal escape detected: {storage_key}")

        return full_path

    def save(
        self,
        data: Union[BinaryIO, bytes],
        storage_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        target_path = self._resolve_safe_path(storage_key, organization_id=organization_id)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            if isinstance(data, bytes):
                with open(target_path, "wb") as f:
                    f.write(data)
                size_bytes = len(data)
            else:
                # Stream file
                bytes_written = 0
                with open(target_path, "wb") as f:
                    while True:
                        chunk = data.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_written += len(chunk)
                size_bytes = bytes_written

            return {
                "storage_key": storage_key,
                "storage_backend": self.backend_name,
                "size_bytes": size_bytes,
                "content_type": content_type,
                "path": target_path
            }
        except Exception as exc:
            raise StorageOperationError(f"Failed to write file to local disk: {exc}")

    def get_stream(self, storage_key: str, organization_id: Optional[str] = None) -> BinaryIO:
        target_path = self._resolve_safe_path(storage_key, organization_id=organization_id)
        if not os.path.isfile(target_path):
            raise StorageNotFoundError(f"Storage key '{storage_key}' not found on local filesystem")
        try:
            return open(target_path, "rb")
        except Exception as exc:
            raise StorageOperationError(f"Failed to open file stream: {exc}")

    def get_bytes(self, storage_key: str, organization_id: Optional[str] = None) -> bytes:
        target_path = self._resolve_safe_path(storage_key, organization_id=organization_id)
        if not os.path.isfile(target_path):
            raise StorageNotFoundError(f"Storage key '{storage_key}' not found on local filesystem")
        try:
            with open(target_path, "rb") as f:
                return f.read()
        except Exception as exc:
            raise StorageOperationError(f"Failed to read file: {exc}")

    def delete(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        target_path = self._resolve_safe_path(storage_key, organization_id=organization_id)
        if not os.path.isfile(target_path):
            return False
        try:
            os.remove(target_path)
            # Optionally remove empty parent directory
            parent = os.path.dirname(target_path)
            if parent != self.base_dir and os.path.isdir(parent) and not os.listdir(parent):
                try:
                    os.rmdir(parent)
                except Exception:
                    pass
            return True
        except Exception as exc:
            raise StorageOperationError(f"Failed to delete file: {exc}")

    def exists(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_key, organization_id=organization_id)
            return os.path.isfile(target_path)
        except Exception:
            return False

    def generate_signed_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a secure HMAC-SHA256 token for local media downloads.
        URL format: /api/v1/media/download-signed?key=...&exp=...&sig=...
        """
        self._resolve_safe_path(storage_key, organization_id=organization_id)
        exp = int(time.time()) + expires_in
        msg = f"{storage_key}:{exp}:{filename or ''}".encode("utf-8")
        sig = hmac.new(self.signing_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        fname_param = f"&filename={filename}" if filename else ""
        return f"/api/v1/media/download-signed?key={storage_key}&exp={exp}&sig={sig}{fname_param}"

    def verify_signed_url(self, storage_key: str, exp: int, sig: str, filename: Optional[str] = None) -> bool:
        """Verify HMAC signature and expiration."""
        if time.time() > exp:
            return False
        msg = f"{storage_key}:{exp}:{filename or ''}".encode("utf-8")
        expected_sig = hmac.new(self.signing_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)

    def list_keys(self, prefix: str = "") -> List[str]:
        """List all storage keys relative to base_dir."""
        keys = []
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.base_dir).replace("\\", "/")
                if not clean_prefix or rel_path.startswith(clean_prefix):
                    keys.append(rel_path)
        return sorted(keys)
