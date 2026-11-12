
from abc import ABC, abstractmethod


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
