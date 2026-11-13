
from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Provider error with retry classification."""

    def __init__(self, message, status_code=None, retryable=False, error_code=None, retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.error_code = error_code
        self.retry_after = retry_after


class BaseChannelAdapter(ABC):

    @abstractmethod
    def validate(self, message):
        """Validate channel-specific message data."""
        pass

    @abstractmethod
    def format_message(self, message):
        """Convert message into provider-specific format."""
        pass

    @abstractmethod
    def send(self, message):
        """Send message through the external provider."""
        pass

    @abstractmethod
    def get_status(self, provider_message_id):
        """Retrieve delivery status from provider."""
        pass

