"""
SenderX Storage Factory
Provides unified instantiation of storage backends based on application configuration.
Strictly prevents silent fallback from S3 to local storage in production.
"""

import os
from typing import Any, Dict, Optional
from flask import current_app, has_app_context

from app.modules.media.storage.base_storage import (
    BaseStorage,
    StorageConfigurationError,
    StorageError,
    StorageNotFoundError,
    StorageOperationError,
    StorageSecurityError,
)
from app.modules.media.storage.local_storage import LocalStorage
from app.modules.media.storage.s3_storage import S3Storage


def get_storage_backend(config: Optional[Dict[str, Any]] = None) -> BaseStorage:
    """
    Factory to retrieve the authoritative BaseStorage backend.
    Enforces strict production safety:
    - Authoritative configuration key is STORAGE_BACKEND.
    - Local filesystem storage is strictly restricted to development/test mode.
    - Production mode must fail closed if S3 configuration is missing.
    - Never silently falls back from S3 to local storage.
    """
    cfg = config or {}
    if not cfg and has_app_context():
        cfg = current_app.config

    app_env = (
        cfg.get("APP_ENV") or
        os.getenv("APP_ENV") or
        "development"
    ).lower().strip()

    # Authoritative configuration: STORAGE_BACKEND takes precedence, with backwards compatibility
    backend_type = (
        cfg.get("STORAGE_BACKEND") or
        cfg.get("MEDIA_STORAGE_BACKEND") or
        os.getenv("STORAGE_BACKEND") or
        os.getenv("MEDIA_STORAGE_BACKEND") or
        "local"
    ).lower().strip()

    # Production safety enforcement
    if app_env == "production":
        if backend_type == "local":
            raise StorageConfigurationError(
                "Local filesystem storage is restricted to development mode and strictly forbidden in production. "
                "Production environment requires S3-compatible object storage (STORAGE_BACKEND='s3')."
            )
        if backend_type != "s3":
            raise StorageConfigurationError(
                f"Production environment requires S3-compatible object storage (STORAGE_BACKEND='s3', got: '{backend_type}')."
            )

    if backend_type == "s3":
        bucket_name = (
            cfg.get("AWS_S3_BUCKET") or
            os.getenv("AWS_S3_BUCKET")
        )
        if not bucket_name:
            raise StorageConfigurationError(
                "S3 storage backend is configured, but required setting 'AWS_S3_BUCKET' is missing. "
                "Production safety policy strictly forbids silent fallback to local storage."
            )

        region = cfg.get("AWS_REGION") or os.getenv("AWS_REGION", "us-east-1")
        access_key = cfg.get("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = cfg.get("AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
        endpoint_url = cfg.get("AWS_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL")
        sse = cfg.get("AWS_S3_SSE", "AES256")

        return S3Storage(
            bucket_name=bucket_name,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
            server_side_encryption=sse
        )

    elif backend_type == "local":
        base_dir = (
            cfg.get("MEDIA_LOCAL_STORAGE_DIR") or
            os.getenv("MEDIA_LOCAL_STORAGE_DIR") or
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage", "uploads")
        )
        secret_key = (
            cfg.get("SECRET_KEY") or
            os.getenv("SECRET_KEY") or
            "senderx-local-secret"
        )
        return LocalStorage(base_dir=base_dir, signing_secret=secret_key)

    else:
        raise StorageConfigurationError(
            f"Unsupported storage backend '{backend_type}'. Supported backends are 'local' and 's3'."
        )


__all__ = [
    "BaseStorage",
    "LocalStorage",
    "S3Storage",
    "StorageError",
    "StorageConfigurationError",
    "StorageNotFoundError",
    "StorageOperationError",
    "StorageSecurityError",
    "get_storage_backend"
]
