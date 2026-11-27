"""Structured exception hierarchy for fail-closed multi-tenant provider resolution."""

from typing import Optional


class ProviderResolutionError(ValueError):
    """
    Raised when resolving or decrypting provider credentials fails.
    Inherits from ValueError to maintain compatibility with existing callers while
    exposing machine-readable error codes and safe HTTP status mappings.
    """

    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_INACTIVE = "PROVIDER_INACTIVE"
    PROVIDER_NOT_AUTHORIZED = "PROVIDER_NOT_AUTHORIZED"
    CREDENTIAL_DECRYPTION_FAILED = "CREDENTIAL_DECRYPTION_FAILED"
    AMBIGUOUS_PROVIDER_CONFIGURATION = "AMBIGUOUS_PROVIDER_CONFIGURATION"
    CHANNEL_PROVIDER_MISMATCH = "CHANNEL_PROVIDER_MISMATCH"

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        provider: Optional[str] = None,
        channel: Optional[str] = None,
        organization_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.error_code = code
        self.message = message
        self.status_code = status_code
        self.provider = provider
        self.channel = channel
        self.organization_id = organization_id

    def to_dict(self):
        return {
            "success": False,
            "error_code": self.code,
            "message": self.message,
        }
