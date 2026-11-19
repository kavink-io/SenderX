"""
SenderX Adapter Registry
Central registry for resolving channel and provider adapters with:
- Tenant isolation and organization-specific configuration lookup
- Production email providers: SendGrid, Amazon SES, SMTP
- Multi-channel mock adapters: Email, SMS, WhatsApp, Telegram
- Explicit error handling for unsupported combinations
- Strict mock/production separation (never silently falls back to mock)
"""

import os
from typing import Optional

from flask import current_app, has_app_context

from app.adapters.email.mock_adapter import MockEmailAdapter
from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.adapters.email.ses_adapter import AmazonSESAdapter
from app.adapters.email.smtp_adapter import SMTPAdapter
from app.adapters.sms.mock_adapter import MockSMSAdapter
from app.adapters.sms.twilio_adapter import TwilioSMSAdapter
from app.adapters.whatsapp.mock_adapter import MockWhatsAppAdapter
from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter
from app.adapters.telegram.mock_adapter import MockTelegramAdapter
from app.adapters.teams.teams_adapter import MicrosoftTeamsAdapter, MockTeamsAdapter
from app.modules.provider_config.service import ProviderConfigService


class AdapterRegistry:

    SUPPORTED_CHANNELS = {"email", "sms", "whatsapp", "telegram", "microsoft_teams", "teams"}
    EMAIL_PROVIDERS = {"mock", "sendgrid", "ses", "amazon_ses", "smtp"}
    SMS_PROVIDERS = {"mock", "twilio"}
    WHATSAPP_PROVIDERS = {"mock", "meta", "whatsapp", "whatsapp_cloud"}
    TEAMS_PROVIDERS = {"mock", "teams", "microsoft_teams", "graph", "msteams"}

    @classmethod
    def get_adapter(cls, provider: str, channel: Optional[str] = None, organization_id: Optional[str] = None):
        """
        Resolve and instantiate the appropriate adapter for a channel, provider, and tenant.
        Strictly enforces tenant credentials and never silently falls back to mock in production.
        """
        if not provider:
            # If no provider specified, check if organization has a configured provider
            if organization_id:
                try:
                    statuses = ProviderConfigService.get_all_configuration_statuses(organization_id=organization_id)
                    if channel == "email" or channel is None:
                        configured_email = [
                            s["provider"] for s in statuses
                            if s.get("configured") and s.get("provider") in cls.EMAIL_PROVIDERS and s.get("provider") != "mock"
                        ]
                        if configured_email:
                            provider = configured_email[0]
                    elif channel == "sms":
                        configured_sms = [
                            s["provider"] for s in statuses
                            if s.get("configured") and s.get("provider") in cls.SMS_PROVIDERS and s.get("provider") != "mock"
                        ]
                        if configured_sms:
                            provider = configured_sms[0]
                    elif channel == "whatsapp":
                        configured_wa = [
                            s["provider"] for s in statuses
                            if s.get("configured") and s.get("provider") in cls.WHATSAPP_PROVIDERS and s.get("provider") != "mock"
                        ]
                        if configured_wa:
                            provider = configured_wa[0]
                    elif channel in ("microsoft_teams", "teams"):
                        configured_teams = [
                            s["provider"] for s in statuses
                            if s.get("configured") and s.get("provider") in cls.TEAMS_PROVIDERS and s.get("provider") != "mock"
                        ]
                        if configured_teams:
                            provider = configured_teams[0]
                except Exception:
                    pass

            if not provider:
                raise ValueError("Provider name is required")

        provider = provider.lower().strip()
        channel = channel.lower().strip() if channel else None

        # --------------------------------------------------
        # 1. MOCK MULTI-CHANNEL PROVIDER
        # --------------------------------------------------
        if provider == "mock":
            environment = (
                current_app.config.get("APP_ENV", "development")
                if has_app_context()
                else os.getenv("APP_ENV", "development")
            )
            if str(environment).strip().lower() == "production":
                raise ValueError("Mock providers are disabled in production")
            if channel == "email" or channel is None:
                return MockEmailAdapter()
            if channel == "sms":
                return MockSMSAdapter()
            if channel == "whatsapp":
                return MockWhatsAppAdapter()
            if channel == "telegram":
                return MockTelegramAdapter()
            if channel in ("microsoft_teams", "teams"):
                return MockTeamsAdapter()

            raise ValueError(
                f"Unsupported channel '{channel}' for mock provider. "
                f"Supported mock channels: {sorted(list(cls.SUPPORTED_CHANNELS))}"
            )

        # --------------------------------------------------
        # 2. SENDGRID PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider == "sendgrid":
            if channel is not None and channel != "email":
                raise ValueError(
                    f"Provider 'sendgrid' only supports 'email' channel, but '{channel}' was requested."
                )

            credentials = None
            try:
                credentials = ProviderConfigService.get_decrypted_configuration(
                    provider,
                    organization_id=organization_id
                )
            except Exception:
                credentials = None

            api_key = credentials.get("api_key") if credentials else None
            from_email = credentials.get("from_email") if credentials else None

            # Platform-level environment fallback
            if not api_key:
                if has_app_context():
                    api_key = current_app.config.get("SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY")
                else:
                    api_key = os.getenv("SENDGRID_API_KEY")

            if not from_email:
                if has_app_context():
                    from_email = current_app.config.get("SENDGRID_FROM_EMAIL") or os.getenv("SENDGRID_FROM_EMAIL")
                else:
                    from_email = os.getenv("SENDGRID_FROM_EMAIL")

            if not api_key or not from_email:
                raise ValueError(
                    "SendGrid configuration not found or incomplete for this organization. "
                    "Configure 'api_key' and 'from_email' via the provider-config API or environment."
                )

            return SendGridAdapter(api_key=api_key, from_email=from_email)

        # --------------------------------------------------
        # 3. AMAZON SES PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider in ("ses", "amazon_ses"):
            if channel is not None and channel != "email":
                raise ValueError(
                    f"Provider '{provider}' only supports 'email' channel, but '{channel}' was requested."
                )

            credentials = None
            try:
                credentials = ProviderConfigService.get_decrypted_configuration(
                    "ses",
                    organization_id=organization_id
                )
                if not credentials:
                    credentials = ProviderConfigService.get_decrypted_configuration(
                        "amazon_ses",
                        organization_id=organization_id
                    )
            except Exception:
                credentials = None

            aws_key = credentials.get("aws_access_key_id") if credentials else None
            aws_secret = credentials.get("aws_secret_access_key") if credentials else None
            from_email = credentials.get("from_email") if credentials else None
            region = credentials.get("aws_region") if credentials else None
            session_token = credentials.get("aws_session_token") if credentials else None

            # Environment fallbacks
            if not aws_key:
                aws_key = os.getenv("AWS_ACCESS_KEY_ID")
            if not aws_secret:
                aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
            if not from_email:
                from_email = os.getenv("AWS_SES_FROM_EMAIL") or os.getenv("SENDGRID_FROM_EMAIL")
            if not region:
                region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
            if not session_token:
                session_token = os.getenv("AWS_SESSION_TOKEN")

            if not aws_key or not aws_secret or not from_email:
                raise ValueError(
                    "Amazon SES configuration not found or incomplete for this organization. "
                    "Configure 'aws_access_key_id', 'aws_secret_access_key', and 'from_email' via provider-config API."
                )

            return AmazonSESAdapter(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                from_email=from_email,
                aws_region=region,
                aws_session_token=session_token
            )

        # --------------------------------------------------
        # 4. SMTP PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider == "smtp":
            if channel is not None and channel != "email":
                raise ValueError(
                    f"Provider 'smtp' only supports 'email' channel, but '{channel}' was requested."
                )

            credentials = None
            try:
                credentials = ProviderConfigService.get_decrypted_configuration(
                    "smtp",
                    organization_id=organization_id
                )
            except Exception:
                credentials = None

            smtp_host = credentials.get("smtp_host") if credentials else None
            smtp_port = credentials.get("smtp_port") if credentials else None
            from_email = credentials.get("from_email") if credentials else None
            smtp_user = credentials.get("smtp_user") if credentials else None
            smtp_password = credentials.get("smtp_password") if credentials else None
            use_tls = credentials.get("use_tls", True) if credentials else True
            use_ssl = credentials.get("use_ssl", False) if credentials else False

            # Environment fallbacks
            if not smtp_host:
                smtp_host = os.getenv("SMTP_HOST")
            if not smtp_port:
                smtp_port = os.getenv("SMTP_PORT") or 587
            if not from_email:
                from_email = os.getenv("SMTP_FROM_EMAIL") or os.getenv("SENDGRID_FROM_EMAIL")
            if not smtp_user:
                smtp_user = os.getenv("SMTP_USER")
            if not smtp_password:
                smtp_password = os.getenv("SMTP_PASSWORD")

            if not smtp_host or not from_email:
                raise ValueError(
                    "SMTP configuration not found or incomplete for this organization. "
                    "Configure 'smtp_host' and 'from_email' via provider-config API or environment."
                )

            return SMTPAdapter(
                smtp_host=smtp_host,
                from_email=from_email,
                smtp_port=int(smtp_port) if smtp_port else 587,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                use_tls=bool(use_tls),
                use_ssl=bool(use_ssl)
            )

        # --------------------------------------------------
        # 5. TWILIO PROVIDER (SMS ONLY)
        # --------------------------------------------------
        if provider == "twilio":
            if channel is not None and channel != "sms":
                raise ValueError(
                    f"Provider 'twilio' only supports 'sms' channel, but '{channel}' was requested."
                )

            credentials = None
            try:
                credentials = ProviderConfigService.get_decrypted_configuration(
                    "twilio",
                    organization_id=organization_id
                )
            except Exception:
                credentials = None

            account_sid = credentials.get("account_sid") if credentials else None
            auth_token = credentials.get("auth_token") if credentials else None
            from_number = credentials.get("from_number") if credentials else None
            messaging_service_sid = credentials.get("messaging_service_sid") if credentials else None
            status_callback_url = credentials.get("status_callback_url") if credentials else None

            # Environment fallbacks
            if not account_sid:
                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            if not auth_token:
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            if not from_number:
                from_number = os.getenv("TWILIO_FROM_NUMBER")
            if not messaging_service_sid:
                messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
            if not status_callback_url:
                status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")

            if not account_sid or not auth_token:
                raise ValueError(
                    "Twilio configuration not found or incomplete for this organization. "
                    "Configure 'account_sid' and 'auth_token' via provider-config API or environment."
                )

            if not from_number and not messaging_service_sid:
                raise ValueError(
                    "Twilio configuration requires either 'from_number' or 'messaging_service_sid' to send SMS messages."
                )

            return TwilioSMSAdapter(
                account_sid=account_sid,
                auth_token=auth_token,
                from_number=from_number,
                messaging_service_sid=messaging_service_sid,
                status_callback_url=status_callback_url
            )

        # --------------------------------------------------
        # 6. META WHATSAPP CLOUD API PROVIDER (WHATSAPP ONLY)
        # --------------------------------------------------
        if provider in ("meta", "whatsapp", "whatsapp_cloud"):
            if channel is not None and channel != "whatsapp":
                raise ValueError(
                    f"Provider '{provider}' only supports 'whatsapp' channel, but '{channel}' was requested."
                )

            credentials = None
            for p_key in (provider, "meta", "whatsapp", "whatsapp_cloud"):
                try:
                    credentials = ProviderConfigService.get_decrypted_configuration(
                        p_key,
                        organization_id=organization_id
                    )
                    if credentials:
                        break
                except Exception:
                    credentials = None

            access_token = credentials.get("access_token") if credentials else None
            phone_number_id = credentials.get("phone_number_id") if credentials else None
            business_account_id = credentials.get("business_account_id") if credentials else None
            graph_api_version = credentials.get("graph_api_version") if credentials else None
            app_secret = credentials.get("app_secret") if credentials else None

            # Environment fallbacks
            if not access_token:
                access_token = os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("META_WHATSAPP_ACCESS_TOKEN")
            if not phone_number_id:
                phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID")
            if not business_account_id:
                business_account_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or os.getenv("META_WABA_ID")
            if not graph_api_version:
                graph_api_version = os.getenv("WHATSAPP_GRAPH_API_VERSION") or "v21.0"
            if not app_secret:
                app_secret = os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET")

            if not access_token or not phone_number_id:
                raise ValueError(
                    "WhatsApp Cloud API configuration not found or incomplete for this organization. "
                    "Configure 'access_token' and 'phone_number_id' via provider-config API or environment."
                )

            return WhatsAppCloudAdapter(
                access_token=access_token,
                phone_number_id=phone_number_id,
                business_account_id=business_account_id,
                graph_api_version=graph_api_version,
                app_secret=app_secret
            )

        # --------------------------------------------------
        # 7. MICROSOFT TEAMS PROVIDER (MICROSOFT GRAPH API)
        # --------------------------------------------------
        if provider in ("teams", "microsoft_teams", "graph", "msteams"):
            if channel is not None and channel not in ("microsoft_teams", "teams"):
                raise ValueError(
                    f"Provider '{provider}' only supports 'microsoft_teams' or 'teams' channel, but '{channel}' was requested."
                )

            credentials = None
            for p_key in (provider, "teams", "microsoft_teams", "graph", "msteams"):
                try:
                    credentials = ProviderConfigService.get_decrypted_configuration(
                        p_key,
                        organization_id=organization_id
                    )
                    if credentials:
                        break
                except Exception:
                    credentials = None

            if credentials and (credentials.get("disconnected") or credentials.get("configured") is False):
                raise ValueError("Microsoft Teams account has been disconnected for this organization. Please reconnect.")

            tenant_id = credentials.get("tenant_id") if credentials else None
            client_id = credentials.get("client_id") if credentials else None
            client_secret = credentials.get("client_secret") if credentials else None
            access_token = credentials.get("access_token") if credentials else None
            refresh_token = credentials.get("refresh_token") if credentials else None
            token_expires_at = credentials.get("token_expires_at") if credentials else None
            default_team_id = credentials.get("default_team_id") if credentials else None
            default_channel_id = credentials.get("default_channel_id") if credentials else None

            # Environment fallbacks
            if not tenant_id:
                tenant_id = os.getenv("TEAMS_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
            if not client_id:
                client_id = os.getenv("TEAMS_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
            if not client_secret:
                client_secret = os.getenv("TEAMS_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
            if not default_team_id:
                default_team_id = os.getenv("TEAMS_DEFAULT_TEAM_ID")
            if not default_channel_id:
                default_channel_id = os.getenv("TEAMS_DEFAULT_CHANNEL_ID")

            if not tenant_id or not client_id or not client_secret:
                raise ValueError(
                    "Microsoft Teams configuration not found or incomplete for this organization. "
                    "Configure 'tenant_id', 'client_id', and 'client_secret' via provider-config API or environment."
                )

            # Auto-persistence callback for delegated token refresh (concurrency-safe)
            def on_token_refresh_callback(new_token_data):
                if organization_id:
                    try:
                        ProviderConfigService.update_refreshed_tokens(
                            provider="teams",
                            new_tokens=new_token_data,
                            organization_id=organization_id
                        )
                    except Exception as err:
                        if has_app_context():
                            current_app.logger.warning("Failed to auto-persist refreshed Teams token: %s", err)

            def credential_loader():
                if organization_id:
                    try:
                        return ProviderConfigService.get_decrypted_configuration("teams", organization_id=organization_id)
                    except Exception:
                        return None
                return None

            allow_local_lock = None
            if has_app_context():
                allow_local_lock = current_app.config.get("TEAMS_ALLOW_LOCAL_LOCK")
                if allow_local_lock is None:
                    allow_local_lock = current_app.config.get("TEAMS_SINGLE_PROCESS_MODE")

            return MicrosoftTeamsAdapter(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                on_token_refresh=on_token_refresh_callback,
                organization_id=organization_id,
                credential_loader=credential_loader,
                allow_local_lock=allow_local_lock,
                default_team_id=default_team_id,
                default_channel_id=default_channel_id
            )

        # --------------------------------------------------
        # 8. UNSUPPORTED PROVIDER
        # --------------------------------------------------
        if channel == "sms":
            supported_list = sorted(list(cls.SMS_PROVIDERS))
            channel_desc = "SMS"
        elif channel == "whatsapp":
            supported_list = sorted(list(cls.WHATSAPP_PROVIDERS))
            channel_desc = "WhatsApp"
        elif channel in ("microsoft_teams", "teams"):
            supported_list = sorted(list(cls.TEAMS_PROVIDERS))
            channel_desc = "Microsoft Teams"
        else:
            supported_list = sorted(list(cls.EMAIL_PROVIDERS))
            channel_desc = "email"

        raise ValueError(
            f"Unsupported provider: '{provider}'"
            + (f" for channel '{channel}'" if channel else "")
            + f". Supported {channel_desc} providers: {supported_list}"
        )
