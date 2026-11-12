
import os

from flask import current_app, has_app_context

from app.adapters.email.mock_adapter import MockEmailAdapter
from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.modules.provider_config.service import ProviderConfigService


class AdapterRegistry:

    @classmethod
    def get_adapter(cls, provider):

        provider = provider.lower().strip()

        # Mock email provider for development and testing
        if provider == "mock":
            return MockEmailAdapter()

        # SendGrid email provider
        if provider == "sendgrid":

            credentials = None

            try:
                credentials = (
                    ProviderConfigService.get_decrypted_configuration(
                        provider
                    )
                )
            except Exception:
                credentials = None

            api_key = credentials.get("api_key") if credentials else None
            from_email = credentials.get("from_email") if credentials else None

            # Get API key from Flask config or environment
            if not api_key:

                if has_app_context():
                    api_key = (
                        current_app.config.get("SENDGRID_API_KEY")
                        or os.getenv("SENDGRID_API_KEY")
                    )
                else:
                    api_key = os.getenv("SENDGRID_API_KEY")

            # Get sender email from Flask config or environment
            if not from_email:

                if has_app_context():
                    from_email = (
                        current_app.config.get("SENDGRID_FROM_EMAIL")
                        or os.getenv("SENDGRID_FROM_EMAIL")
                    )
                else:
                    from_email = os.getenv("SENDGRID_FROM_EMAIL")

            # Validate SendGrid configuration
            if not api_key or not from_email:
                raise ValueError(
                    "SendGrid configuration not found or incomplete. "
                    "Configure 'SENDGRID_API_KEY' and "
                    "'SENDGRID_FROM_EMAIL' in your .env file, "
                    "or save it via the provider-config API."
                )

            return SendGridAdapter(
                api_key=api_key,
                from_email=from_email
            )

        # Unsupported provider
        raise ValueError(
            f"Unsupported provider: {provider}"
        )
