"""
SenderX Media Storage Base Interface & Exceptions
Defines abstract storage provider methods and error hierarchy.
"""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Dict, List, Optional, Union


class StorageError(Exception):
    """Base exception for all storage-related errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "STORAGE_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class StorageConfigurationError(StorageError):
    """Raised when storage configuration is invalid or missing required credentials."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500, error_code="STORAGE_CONFIG_ERROR")


class StorageNotFoundError(StorageError):
    """Raised when a requested storage key does not exist."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404, error_code="STORAGE_KEY_NOT_FOUND")


class StorageSecurityError(StorageError):
    """Raised on path traversal or unauthorized access attempt."""
    def __init__(self, message: str):
        super().__init__(message, status_code=403, error_code="STORAGE_SECURITY_VIOLATION")


class StorageOperationError(StorageError):
    """Raised when an I/O or network operation on the storage backend fails."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code, error_code="STORAGE_OPERATION_FAILED")


class BaseStorage(ABC):
    """
    Abstract interface for object and filesystem storage backends.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Name of storage backend (e.g., 'local', 's3')."""
        pass

    @abstractmethod
    def save(
        self,
        data: Union[BinaryIO, bytes],
        storage_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store file content at storage_key.
        Returns a dictionary with storage_key, backend_name, size_bytes, etc.
        """
        pass

    @abstractmethod
    def get_stream(self, storage_key: str, organization_id: Optional[str] = None) -> BinaryIO:
        """
        Open and return a readable binary stream for storage_key.
        Raises StorageNotFoundError if key does not exist.
        """
        pass

    @abstractmethod
    def get_bytes(self, storage_key: str, organization_id: Optional[str] = None) -> bytes:
        """
        Read and return the complete raw byte contents of storage_key.
        Raises StorageNotFoundError if key does not exist.
        """
        pass

    @abstractmethod
    def delete(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        """
        Delete file at storage_key.
        Returns True if deleted, False if not found.
        """
        pass

    @abstractmethod
    def exists(self, storage_key: str, organization_id: Optional[str] = None) -> bool:
        """
        Check if file at storage_key exists.
        """
        pass

    @abstractmethod
    def generate_signed_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a pre-signed or temporary secure download URL for storage_key.
        """
        pass

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """
        List storage keys matching prefix.
        """
        pass
