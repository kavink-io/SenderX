"""
SenderX Adapter Registry
Central registry for resolving channel and provider adapters with:
- Strict fail-closed multi-tenant credential isolation
- Zero implicit platform or environment fallbacks for organizations
- Explicit PlatformProviderPolicy authorization for platform routing
- Production email, SMS, WhatsApp Cloud, and Microsoft Teams providers
- Structured ProviderResolutionError codes
"""

import os
from typing import Dict, List, Optional, Tuple

from flask import current_app, has_app_context

from app.adapters.errors import ProviderResolutionError
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
from app.modules.provider_config.service import (
    PlatformProviderPolicy,
    ProviderConfigService,
)


class AdapterRegistry:

    SUPPORTED_CHANNELS = {"email", "sms", "whatsapp", "telegram", "microsoft_teams", "teams"}
    EMAIL_PROVIDERS = {"mock", "sendgrid", "ses", "amazon_ses", "smtp"}
    SMS_PROVIDERS = {"mock", "twilio"}
    WHATSAPP_PROVIDERS = {"mock", "meta", "whatsapp", "whatsapp_cloud"}
    TEAMS_PROVIDERS = {"mock", "teams", "microsoft_teams", "graph", "msteams"}

    CANONICAL_PROVIDER_FAMILY = {
        "sendgrid": "sendgrid",
        "ses": "ses",
        "amazon_ses": "ses",
        "smtp": "smtp",
        "twilio": "twilio",
        "meta": "whatsapp",
        "whatsapp": "whatsapp",
        "whatsapp_cloud": "whatsapp",
        "teams": "teams",
        "microsoft_teams": "teams",
        "graph": "teams",
        "msteams": "teams",
    }

    @classmethod
    def _canonical_channel(cls, channel: Optional[str]) -> Optional[str]:
        if channel is None:
            return None
        clean = str(channel).strip().lower()
        if clean in ("microsoft_teams", "msteams"):
            return "teams"
        return clean

    @classmethod
    def _providers_for_channel(cls, channel: Optional[str]) -> set:
        canon = cls._canonical_channel(channel)
        if canon in (None, "email"):
            return cls.EMAIL_PROVIDERS - {"mock"}
        if canon == "sms":
            return cls.SMS_PROVIDERS - {"mock"}
        if canon == "whatsapp":
            return cls.WHATSAPP_PROVIDERS - {"mock"}
        if canon == "teams":
            return cls.TEAMS_PROVIDERS - {"mock"}
        return set()

    @classmethod
    def _validate_channel_provider_pair(cls, provider: str, channel: Optional[str]):
        canon_channel = cls._canonical_channel(channel)
        if canon_channel is not None and channel not in cls.SUPPORTED_CHANNELS:
            raise ProviderResolutionError(
                code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                message=f"Unsupported channel '{channel}'",
                status_code=400,
                provider=provider,
                channel=channel,
            )

        if provider == "mock":
            if canon_channel is not None and channel not in cls.SUPPORTED_CHANNELS:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                    message=f"Unsupported channel '{channel}' for mock provider.",
                    status_code=400,
                    provider=provider,
                    channel=channel,
                )
            return

        if provider == "sendgrid" or provider in ("ses", "amazon_ses") or provider == "smtp":
            if canon_channel is not None and canon_channel != "email":
                raise ProviderResolutionError(
                    code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                    message=f"Provider '{provider}' only supports 'email' channel, but '{channel}' was requested.",
                    status_code=400,
                    provider=provider,
                    channel=channel,
                )
        elif provider == "twilio":
            if canon_channel is not None and canon_channel != "sms":
                raise ProviderResolutionError(
                    code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                    message=f"Provider '{provider}' only supports 'sms' channel, but '{channel}' was requested.",
                    status_code=400,
                    provider=provider,
                    channel=channel,
                )
        elif provider in ("meta", "whatsapp", "whatsapp_cloud"):
            if canon_channel is not None and canon_channel != "whatsapp":
                raise ProviderResolutionError(
                    code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                    message=f"Provider '{provider}' only supports 'whatsapp' channel, but '{channel}' was requested.",
                    status_code=400,
                    provider=provider,
                    channel=channel,
                )
        elif provider in ("teams", "microsoft_teams", "graph", "msteams"):
            if canon_channel is not None and canon_channel != "teams":
                raise ProviderResolutionError(
                    code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                    message=f"Provider '{provider}' only supports 'microsoft_teams' or 'teams' channel, but '{channel}' was requested.",
                    status_code=400,
                    provider=provider,
                    channel=channel,
                )

    @classmethod
    def _resolve_provider_when_omitted(
        cls,
        channel: Optional[str],
        organization_id: Optional[str],
        allow_platform_fallback: bool = False,
        **kwargs,
    ) -> str:
        canon_channel = cls._canonical_channel(channel)
        allowed_providers = cls._providers_for_channel(canon_channel)

        if not organization_id:
            if allow_platform_fallback:
                statuses = ProviderConfigService.get_all_configuration_statuses(organization_id=None)
                active_families: Dict[str, str] = {}
                for doc in statuses:
                    prov = str(doc.get("provider") or "").lower().strip()
                    if prov in allowed_providers and ProviderConfigService._is_document_active(doc):
                        family = cls.CANONICAL_PROVIDER_FAMILY.get(prov, prov)
                        active_families.setdefault(family, prov)
                if len(active_families) == 1:
                    return next(iter(active_families.values()))
                if len(active_families) > 1:
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION,
                        message=(
                            f"Multiple platform providers are configured for channel '{channel}'. "
                            "Specify an explicit provider."
                        ),
                        status_code=400,
                        channel=channel,
                    )
            raise ProviderResolutionError(
                code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                message="Provider name is required",
                status_code=400,
                channel=channel,
            )

        # Organization-scoped unambiguous resolution
        statuses = ProviderConfigService.get_all_configuration_statuses(organization_id=organization_id)
        active_families: Dict[str, str] = {}
        inactive_found = False

        for doc in statuses:
            prov = str(doc.get("provider") or "").lower().strip()
            if prov not in allowed_providers:
                continue
            if ProviderConfigService._is_document_active(doc):
                family = cls.CANONICAL_PROVIDER_FAMILY.get(prov, prov)
                active_families.setdefault(family, prov)
            else:
                inactive_found = True

        if canon_channel == "whatsapp" and has_app_context() and getattr(current_app, "mongo_db", None) is not None:
            from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
            wa_active = WhatsAppIntegrationRepository.find_active_by_organization(organization_id)
            int_id = kwargs.get("integration_id") or kwargs.get("whatsapp_integration_id")
            from_phone = kwargs.get("from_phone_number_id") or kwargs.get("from")
            if len(wa_active) > 1 and not (int_id or from_phone):
                raise ProviderResolutionError(
                    code=ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION,
                    message=(
                        "Multiple active WhatsApp integrations exist for this organization. "
                        "Specify 'whatsapp_integration_id' or 'from_phone_number_id'."
                    ),
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=organization_id,
                )
            if len(wa_active) >= 1 or int_id or from_phone:
                active_families.setdefault("whatsapp", "whatsapp")

        if len(active_families) > 1:
            raise ProviderResolutionError(
                code=ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION,
                message=(
                    f"Multiple active providers ({', '.join(sorted(active_families.keys()))}) are configured "
                    f"for channel '{channel}' in this organization. Specify an explicit provider."
                ),
                status_code=400,
                channel=channel,
                organization_id=organization_id,
            )

        if len(active_families) == 1:
            return next(iter(active_families.values()))

        if inactive_found:
            raise ProviderResolutionError(
                code=ProviderResolutionError.PROVIDER_INACTIVE,
                message=f"All configured providers for channel '{channel}' are inactive or disconnected for this organization",
                status_code=400,
                channel=channel,
                organization_id=organization_id,
            )

        if allow_platform_fallback:
            if not PlatformProviderPolicy.is_authorized(organization_id, channel=canon_channel):
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                    message=f"Organization is not authorized to use platform credentials for channel '{channel}'",
                    status_code=403,
                    channel=channel,
                    organization_id=organization_id,
                )
            statuses_platform = ProviderConfigService.get_all_configuration_statuses(organization_id=None)
            plat_families: Dict[str, str] = {}
            for doc in statuses_platform:
                prov = str(doc.get("provider") or "").lower().strip()
                if prov in allowed_providers and ProviderConfigService._is_document_active(doc):
                    family = cls.CANONICAL_PROVIDER_FAMILY.get(prov, prov)
                    plat_families.setdefault(family, prov)
            if len(plat_families) > 1:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION,
                    message=f"Multiple platform providers are configured for channel '{channel}'. Specify an explicit provider.",
                    status_code=400,
                    channel=channel,
                    organization_id=organization_id,
                )
            if len(plat_families) == 1:
                return next(iter(plat_families.values()))

        raise ProviderResolutionError(
            code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
            message=f"No active provider is configured for channel '{channel}' in this organization",
            status_code=400,
            channel=channel,
            organization_id=organization_id,
        )

    @classmethod
    def _load_db_credentials(
        cls,
        provider_keys: Tuple[str, ...],
        organization_id: Optional[str],
        channel: Optional[str],
        allow_platform_fallback: bool = False,
    ) -> Tuple[Optional[dict], bool]:
        """
        Resolve DB credentials strictly for `(provider_keys, organization_id)`.
        Returns `(credentials_dict_or_None, used_authorized_platform)`.
        Never catches `ProviderResolutionError` (e.g., inactive/decryption/auth failures).
        """
        inactive_error = None
        for p_key in dict.fromkeys(k for k in provider_keys if k):
            try:
                creds = ProviderConfigService.get_decrypted_configuration(
                    p_key,
                    organization_id=organization_id,
                    allow_platform_fallback=False,
                )
                if creds:
                    return creds, False
            except ProviderResolutionError as err:
                if err.code == ProviderResolutionError.PROVIDER_INACTIVE:
                    inactive_error = err
                    continue
                raise

        if inactive_error is not None:
            raise inactive_error

        # Explicit platform fallback only when requested and organization is policy-authorized.
        if organization_id is not None and allow_platform_fallback:
            primary_provider = provider_keys[0]
            if not PlatformProviderPolicy.is_authorized(
                organization_id,
                provider=primary_provider,
                channel=cls._canonical_channel(channel),
            ):
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                    message=(
                        f"Organization is not authorized to use platform credentials "
                        f"for provider '{primary_provider}'"
                    ),
                    status_code=403,
                    provider=primary_provider,
                    channel=channel,
                    organization_id=organization_id,
                )
            for p_key in dict.fromkeys(k for k in provider_keys if k):
                creds = ProviderConfigService.get_decrypted_configuration(
                    p_key,
                    organization_id=None,
                    allow_platform_fallback=False,
                )
                if creds:
                    return creds, True

        return None, False

    @classmethod
    def get_adapter(
        cls,
        provider: Optional[str],
        channel: Optional[str] = None,
        organization_id: Optional[str] = None,
        allow_platform_fallback: bool = False,
        allow_env_fallback: Optional[bool] = None,
        **kwargs,
    ):
        """
        Resolve and instantiate the appropriate adapter for a channel, provider, and tenant.
        Fail closed for organization dispatches: never uses global env credentials or
        another organization's configuration.
        """
        # Prevent blank/whitespace or non-string tenant IDs from degrading to platform scope.
        if organization_id is not None:
            if not isinstance(organization_id, str) or not organization_id.strip():
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                    message="Valid organization_id is required for tenant provider resolution",
                    status_code=403,
                    provider=provider,
                    channel=channel,
                )
            organization_id = organization_id.strip()

        channel = channel.lower().strip() if isinstance(channel, str) and channel.strip() else None

        # Environment fallback is strictly limited to explicit platform calls (`organization_id is None`).
        can_use_platform_env = (
            organization_id is None and (True if allow_env_fallback is None else bool(allow_env_fallback))
        )

        if not provider or not str(provider).strip():
            provider = cls._resolve_provider_when_omitted(
                channel=channel,
                organization_id=organization_id,
                allow_platform_fallback=allow_platform_fallback,
                **kwargs,
            )

        provider = str(provider).lower().strip()
        cls._validate_channel_provider_pair(provider, channel)

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
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                    message="Mock providers are disabled in production",
                    status_code=403,
                    provider=provider,
                    channel=channel,
                    organization_id=organization_id,
                )
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

            raise ProviderResolutionError(
                code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
                message=(
                    f"Unsupported channel '{channel}' for mock provider. "
                    f"Supported mock channels: {sorted(list(cls.SUPPORTED_CHANNELS))}"
                ),
                status_code=400,
                provider=provider,
                channel=channel,
            )

        # --------------------------------------------------
        # 2. SENDGRID PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider == "sendgrid":
            credentials, _ = cls._load_db_credentials(
                ("sendgrid",),
                organization_id=organization_id,
                channel=channel or "email",
                allow_platform_fallback=allow_platform_fallback,
            )

            api_key = credentials.get("api_key") if credentials else None
            from_email = credentials.get("from_email") if credentials else None

            if not credentials and can_use_platform_env:
                if has_app_context():
                    api_key = current_app.config.get("SENDGRID_API_KEY") or os.getenv("SENDGRID_API_KEY")
                    from_email = current_app.config.get("SENDGRID_FROM_EMAIL") or os.getenv("SENDGRID_FROM_EMAIL")
                else:
                    api_key = os.getenv("SENDGRID_API_KEY")
                    from_email = os.getenv("SENDGRID_FROM_EMAIL")

            if not api_key or not from_email:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "SendGrid configuration not found or incomplete for this organization. "
                        "Configure 'api_key' and 'from_email' via the organization provider-config API."
                    ),
                    status_code=400,
                    provider=provider,
                    channel=channel or "email",
                    organization_id=organization_id,
                )

            return SendGridAdapter(api_key=api_key, from_email=from_email)

        # --------------------------------------------------
        # 3. AMAZON SES PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider in ("ses", "amazon_ses"):
            credentials, _ = cls._load_db_credentials(
                ("ses", "amazon_ses"),
                organization_id=organization_id,
                channel=channel or "email",
                allow_platform_fallback=allow_platform_fallback,
            )

            aws_key = credentials.get("aws_access_key_id") if credentials else None
            aws_secret = credentials.get("aws_secret_access_key") if credentials else None
            from_email = credentials.get("from_email") if credentials else None
            region = credentials.get("aws_region") if credentials else None
            session_token = credentials.get("aws_session_token") if credentials else None

            if not credentials and can_use_platform_env:
                aws_key = os.getenv("AWS_ACCESS_KEY_ID")
                aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
                from_email = os.getenv("AWS_SES_FROM_EMAIL")
                region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
                session_token = os.getenv("AWS_SESSION_TOKEN")

            if not region:
                region = "us-east-1"

            if not aws_key or not aws_secret or not from_email:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "Amazon SES configuration not found or incomplete for this organization. "
                        "Configure 'aws_access_key_id', 'aws_secret_access_key', and 'from_email' via provider-config API."
                    ),
                    status_code=400,
                    provider=provider,
                    channel=channel or "email",
                    organization_id=organization_id,
                )

            return AmazonSESAdapter(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                from_email=from_email,
                aws_region=region,
                aws_session_token=session_token,
            )

        # --------------------------------------------------
        # 4. SMTP PROVIDER (EMAIL ONLY)
        # --------------------------------------------------
        if provider == "smtp":
            credentials, _ = cls._load_db_credentials(
                ("smtp",),
                organization_id=organization_id,
                channel=channel or "email",
                allow_platform_fallback=allow_platform_fallback,
            )

            smtp_host = credentials.get("smtp_host") if credentials else None
            smtp_port = credentials.get("smtp_port") if credentials else None
            from_email = credentials.get("from_email") if credentials else None
            smtp_user = credentials.get("smtp_user") if credentials else None
            smtp_password = credentials.get("smtp_password") if credentials else None
            use_tls = credentials.get("use_tls", True) if credentials else True
            use_ssl = credentials.get("use_ssl", False) if credentials else False

            if not credentials and can_use_platform_env:
                smtp_host = os.getenv("SMTP_HOST")
                smtp_port = os.getenv("SMTP_PORT") or 587
                from_email = os.getenv("SMTP_FROM_EMAIL")
                smtp_user = os.getenv("SMTP_USER")
                smtp_password = os.getenv("SMTP_PASSWORD")

            if not smtp_host or not from_email:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "SMTP configuration not found or incomplete for this organization. "
                        "Configure 'smtp_host' and 'from_email' via the organization provider-config API."
                    ),
                    status_code=400,
                    provider=provider,
                    channel=channel or "email",
                    organization_id=organization_id,
                )

            return SMTPAdapter(
                smtp_host=smtp_host,
                from_email=from_email,
                smtp_port=int(smtp_port) if smtp_port else 587,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                use_tls=bool(use_tls),
                use_ssl=bool(use_ssl),
            )

        # --------------------------------------------------
        # 5. TWILIO PROVIDER (SMS ONLY)
        # --------------------------------------------------
        if provider == "twilio":
            credentials, _ = cls._load_db_credentials(
                ("twilio",),
                organization_id=organization_id,
                channel=channel or "sms",
                allow_platform_fallback=allow_platform_fallback,
            )

            account_sid = credentials.get("account_sid") if credentials else None
            auth_token = credentials.get("auth_token") if credentials else None
            from_number = credentials.get("from_number") if credentials else None
            messaging_service_sid = credentials.get("messaging_service_sid") if credentials else None
            status_callback_url = credentials.get("status_callback_url") if credentials else None

            if not credentials and can_use_platform_env:
                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                from_number = os.getenv("TWILIO_FROM_NUMBER")
                messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
                status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")

            if not account_sid or not auth_token:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "Twilio configuration not found or incomplete for this organization. "
                        "Configure 'account_sid' and 'auth_token' via the organization provider-config API."
                    ),
                    status_code=400,
                    provider=provider,
                    channel=channel or "sms",
                    organization_id=organization_id,
                )

            if not from_number and not messaging_service_sid:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message="Twilio configuration requires either 'from_number' or 'messaging_service_sid' to send SMS messages.",
                    status_code=400,
                    provider=provider,
                    channel=channel or "sms",
                    organization_id=organization_id,
                )

            return TwilioSMSAdapter(
                account_sid=account_sid,
                auth_token=auth_token,
                from_number=from_number,
                messaging_service_sid=messaging_service_sid,
                status_callback_url=status_callback_url,
            )

        # --------------------------------------------------
        # 6. META WHATSAPP CLOUD API PROVIDER (WHATSAPP ONLY)
        # --------------------------------------------------
        if provider in ("meta", "whatsapp", "whatsapp_cloud"):
            credentials = None

            if organization_id:
                from app.modules.whatsapp.service import WhatsAppIntegrationService
                try:
                    credentials = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
                        organization_id=organization_id,
                        integration_id=kwargs.get("integration_id") or kwargs.get("whatsapp_integration_id"),
                        from_phone_number_id=kwargs.get("from_phone_number_id") or kwargs.get("from"),
                        allow_platform_fallback=allow_platform_fallback,
                    )
                except ProviderResolutionError:
                    raise
                except ValueError as wa_err:
                    err_str = str(wa_err)
                    if "Multiple active WhatsApp integrations" in err_str:
                        code = ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION
                        status_code = 400
                    elif "not found or access denied" in err_str:
                        code = ProviderResolutionError.PROVIDER_NOT_AUTHORIZED
                        status_code = 403
                    elif "is disconnected or inactive" in err_str:
                        code = ProviderResolutionError.PROVIDER_INACTIVE
                        status_code = 400
                    else:
                        code = ProviderResolutionError.PROVIDER_NOT_CONFIGURED
                        status_code = 400
                    raise ProviderResolutionError(
                        code=code,
                        message=err_str,
                        status_code=status_code,
                        provider=provider,
                        channel="whatsapp",
                        organization_id=organization_id,
                    ) from wa_err
            else:
                credentials, _ = cls._load_db_credentials(
                    (provider, "meta", "whatsapp", "whatsapp_cloud"),
                    organization_id=None,
                    channel="whatsapp",
                    allow_platform_fallback=False,
                )
                if not credentials and can_use_platform_env:
                    credentials = {
                        "access_token": os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("META_WHATSAPP_ACCESS_TOKEN"),
                        "phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID"),
                        "business_account_id": os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or os.getenv("META_WABA_ID"),
                        "graph_api_version": os.getenv("WHATSAPP_GRAPH_API_VERSION") or "v21.0",
                        "app_secret": os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET"),
                    }

            access_token = credentials.get("access_token") if credentials else None
            phone_number_id = credentials.get("phone_number_id") if credentials else None
            business_account_id = credentials.get("business_account_id") if credentials else None
            graph_api_version = (credentials.get("graph_api_version") if credentials else None) or "v21.0"
            app_secret = credentials.get("app_secret") if credentials else None

            if not access_token or not phone_number_id:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "WhatsApp Cloud API configuration not found or incomplete for this organization. "
                        "Configure a connected WhatsApp integration for this organization."
                    ),
                    status_code=400,
                    provider=provider,
                    channel="whatsapp",
                    organization_id=organization_id,
                )

            return WhatsAppCloudAdapter(
                access_token=access_token,
                phone_number_id=phone_number_id,
                business_account_id=business_account_id,
                graph_api_version=graph_api_version,
                app_secret=app_secret,
            )

        # --------------------------------------------------
        # 7. MICROSOFT TEAMS PROVIDER (MICROSOFT GRAPH API)
        # --------------------------------------------------
        if provider in ("teams", "microsoft_teams", "graph", "msteams"):
            credentials, _ = cls._load_db_credentials(
                (provider, "teams", "microsoft_teams", "graph", "msteams"),
                organization_id=organization_id,
                channel=channel or "teams",
                allow_platform_fallback=allow_platform_fallback,
            )

            tenant_id = credentials.get("tenant_id") if credentials else None
            client_id = credentials.get("client_id") if credentials else None
            client_secret = credentials.get("client_secret") if credentials else None
            access_token = credentials.get("access_token") if credentials else None
            refresh_token = credentials.get("refresh_token") if credentials else None
            token_expires_at = credentials.get("token_expires_at") if credentials else None
            default_team_id = credentials.get("default_team_id") if credentials else None
            default_channel_id = credentials.get("default_channel_id") if credentials else None

            if not credentials and can_use_platform_env:
                tenant_id = os.getenv("TEAMS_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
                client_id = os.getenv("TEAMS_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
                client_secret = os.getenv("TEAMS_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
                default_team_id = os.getenv("TEAMS_DEFAULT_TEAM_ID")
                default_channel_id = os.getenv("TEAMS_DEFAULT_CHANNEL_ID")

            if not tenant_id or not client_id or not client_secret:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=(
                        "Microsoft Teams configuration not found or incomplete for this organization. "
                        "Configure 'tenant_id', 'client_id', and 'client_secret' via the organization provider-config API."
                    ),
                    status_code=400,
                    provider=provider,
                    channel=channel or "teams",
                    organization_id=organization_id,
                )

            def on_token_refresh_callback(new_token_data):
                if organization_id:
                    try:
                        ProviderConfigService.update_refreshed_tokens(
                            provider="teams",
                            new_tokens=new_token_data,
                            organization_id=organization_id,
                        )
                    except Exception as err:
                        if has_app_context():
                            current_app.logger.warning(
                                "Failed to auto-persist refreshed Teams token (%s)",
                                type(err).__name__,
                            )

            def credential_loader():
                if organization_id:
                    try:
                        return ProviderConfigService.get_decrypted_configuration(
                            "teams",
                            organization_id=organization_id,
                            allow_platform_fallback=False,
                        )
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
                default_channel_id=default_channel_id,
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

        raise ProviderResolutionError(
            code=ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH,
            message=(
                f"Unsupported provider: '{provider}'"
                + (f" for channel '{channel}'" if channel else "")
                + f". Supported {channel_desc} providers: {supported_list}"
            ),
            status_code=400,
            provider=provider,
            channel=channel,
            organization_id=organization_id,
        )
