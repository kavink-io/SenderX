"""
SenderX S3-Compatible Object Storage Backend
Production object storage implementation using Amazon S3 or S3-compatible APIs
(MinIO, Ceph, Cloudflare R2, Google Cloud Storage XML/S3).
Enforces encryption, pre-signed download URLs, and explicit configuration
(never silently falls back to local storage).
"""

import io
from typing import Any, BinaryIO, Dict, List, Optional, Union
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, BotoCoreError

from app.modules.media.storage.base_storage import (
    BaseStorage,
    StorageConfigurationError,
    StorageNotFoundError,
    StorageOperationError,
    StorageSecurityError,
)


class S3Storage(BaseStorage):
    """
    Production-grade S3 object storage backend.
    """

    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        server_side_encryption: Optional[str] = "AES256",
        s3_client: Optional[Any] = None
    ):
        if not bucket_name or not isinstance(bucket_name, str) or not bucket_name.strip():
            raise StorageConfigurationError(
                "S3Storage requires a valid 'bucket_name'. Cannot initialize S3 storage backend."
            )

        self.bucket_name = bucket_name.strip()
        self.region_name = (region_name or "us-east-1").strip()
        self.endpoint_url = endpoint_url.strip() if endpoint_url else None
        self.server_side_encryption = server_side_encryption

        if s3_client is not None:
            self._s3_client = s3_client
        else:
            client_kwargs: Dict[str, Any] = {
                "region_name": self.region_name,
                "config": BotoConfig(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=30
                )
            }
            if aws_access_key_id and aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = aws_access_key_id.strip()
                client_kwargs["aws_secret_access_key"] = aws_secret_access_key.strip()
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            try:
                self._s3_client = boto3.client("s3", **client_kwargs)
            except Exception as exc:
                raise StorageConfigurationError(f"Failed to initialize Boto3 S3 client: {exc}")

    @property
    def backend_name(self) -> str:
        return "s3"

    def _validate_key(self, storage_key: str, organization_id: Optional[str] = None) -> str:
        if not storage_key or not isinstance(storage_key, str):
            raise StorageSecurityError("Storage key must be a non-empty string")
        if "\x00" in storage_key:
            raise StorageSecurityError("Storage key contains invalid null bytes")
        clean_key = storage_key.strip().replace("\\", "/").lstrip("/")
        parts = clean_key.split("/")
        if any(part in ("..", ".") for part in parts):
            raise StorageSecurityError(f"Path traversal detected in S3 storage key: {storage_key}")

        if organization_id:
            expected_prefix = f"orgs/{organization_id}/"
            if not clean_key.startswith(expected_prefix):
                raise StorageSecurityError(
                    f"Cross-tenant storage access violation: storage key does not belong to organization '{organization_id}'"
                )

        return clean_key

    def save(
        self,
        data: Union[BinaryIO, bytes],
        storage_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        key = self._validate_key(storage_key, organization_id=organization_id)

        # Enforce private bucket access and server-side encryption
        extra_args: Dict[str, Any] = {
            "ContentType": content_type,
            "ACL": "private"
        }
        if self.server_side_encryption:
            extra_args["ServerSideEncryption"] = self.server_side_encryption
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        try:
            if isinstance(data, bytes):
                size_bytes = len(data)
                body = io.BytesIO(data)
            else:
                body = data
                try:
                    orig_pos = body.tell()
                    body.seek(0, io.SEEK_END)
                    size_bytes = body.tell()
                    body.seek(orig_pos, io.SEEK_SET)
                except Exception:
                    size_bytes = -1

            self._s3_client.upload_fileobj(
                Fileobj=body,
                Bucket=self.bucket_name,
                Key=key,
                ExtraArgs=extra_args
            )

            return {
                "storage_key": key,
                "storage_backend": self.backend_name,
                "bucket": self.bucket_name,
                "size_bytes": size_bytes,
                "content_type": content_type,
                "encryption": self.server_side_encryption
            }
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise StorageOperationError(f"S3 upload error ({code}): {exc}")
        except Exception as exc:
            raise StorageOperationError(f"Failed to upload object to S3: {exc}")

    def get_stream(self, storage_key: str, organization_id: Optional[str] = None) -> BinaryIO:
        key = self._validate_key(storage_key, organization_id=organization_id)
        try:
            resp = self._s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return resp["Body"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise StorageNotFoundError(f"S3 object '{key}' not found in bucket '{self.bucket_name}'")
            raise StorageOperationError(f"S3 get_object error ({code}): {exc}")
        except Exception as exc:
            raise StorageOperationError(f"Failed to retrieve object stream from S3: {exc}")

    def get_bytes(self, storage_key: str, organization_id: Optional[str] = None) -> bytes:
        stream = self.get_stream(storage_key, organization_id=organization_id)
        try:
            return stream.read()
        except Exception as exc:
            raise StorageOperationError(f"Failed to read S3 object data: {exc}")

    def delete(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        key = self._validate_key(storage_key, organization_id=organization_id)
        try:
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as exc:
            raise StorageOperationError(f"S3 delete_object error: {exc}")
        except Exception as exc:
            raise StorageOperationError(f"Failed to delete S3 object: {exc}")

    def exists(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        try:
            key = self._validate_key(storage_key, organization_id=organization_id)
            self._s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def generate_signed_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Optional[str]:
        key = self._validate_key(storage_key, organization_id=organization_id)
        # Cap pre-signed URL expiration at 3600s (1 hour) max for security
        safe_expires_in = min(max(60, int(expires_in)), 3600)

        params: Dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key
        }
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        try:
            url = self._s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=safe_expires_in
            )
            return url
        except Exception as exc:
            raise StorageOperationError(f"Failed to generate S3 pre-signed URL: {exc}")

    def list_keys(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        keys: List[str] = []
        paginator = self._s3_client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=clean_prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return sorted(keys)
        except Exception as exc:
            raise StorageOperationError(f"Failed to list S3 objects: {exc}")
