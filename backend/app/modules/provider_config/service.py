
import json
import os
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from flask import current_app, has_app_context

from app.adapters.base_adapter import ProviderError
from app.adapters.errors import ProviderResolutionError
from app.adapters.teams.teams_utils import (
    generate_oauth_state,
    validate_oauth_state,
    generate_pkce_pair,
    verify_pkce,
    is_redirect_uri_allowed,
    verify_microsoft_id_token,
    TEAMS_DELEGATED_SCOPES,
)
from app.adapters.teams.graph_client import (
    generate_authorization_url,
    exchange_code_for_tokens,
    get_user_profile,
)


class PlatformProviderPolicy:
    """
    Explicit authorization gate controlling whether an organization may route
    through platform-level provider credentials (`organization_id=None`).
    Never allows implicit fallback.
    """

    @staticmethod
    def is_authorized(organization_id, provider=None, channel=None):
        if not organization_id or not isinstance(organization_id, str) or not organization_id.strip():
            return False

        clean_org_id = organization_id.strip()
        if not has_app_context() or not getattr(current_app, "mongo_db", None):
            return False

        db = current_app.mongo_db
        try:
            org_col = db["organizations"]
        except Exception:
            return False

        if not hasattr(org_col, "find_one"):
            return False

        org = org_col.find_one({"organization_id": clean_org_id})
        if not org or str(org.get("status", "")).upper() != "ACTIVE":
            return False

        if org.get("allow_platform_provider_routing") is True:
            return True

        clean_provider = str(provider).lower().strip() if provider else None
        clean_channel = str(channel).lower().strip() if channel else None

        allowed_providers = org.get("authorized_platform_providers")
        if clean_provider and isinstance(allowed_providers, (list, tuple, set)):
            if clean_provider in {str(p).lower().strip() for p in allowed_providers if p}:
                return True

        allowed_channels = org.get("authorized_platform_channels")
        if clean_channel and isinstance(allowed_channels, (list, tuple, set)):
            if clean_channel in {str(c).lower().strip() for c in allowed_channels if c}:
                return True

        return False


class ProviderConfigService:

    INACTIVE_STATUSES = {"INACTIVE", "DISABLED", "DISCONNECTED", "REVOKED"}

    @classmethod
    def _get_fernet_instances(cls):
        """
        Load primary Fernet key and optional previous rotation keys cleanly.
        Returns (primary_fernet, multi_fernet, key_version).
        """
        primary_key = None
        previous_keys_raw = None
        key_version = "v1"

        if has_app_context():
            primary_key = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY")
            previous_keys_raw = current_app.config.get("CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS")
            key_version = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY_VERSION", "v1")

        if not primary_key:
            primary_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        if not previous_keys_raw:
            previous_keys_raw = os.getenv("CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS", "")
        if not key_version or key_version == "v1":
            key_version = os.getenv("CREDENTIAL_ENCRYPTION_KEY_VERSION", "v1")

        if not primary_key:
            raise ProviderResolutionError(
                code=ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED,
                message="Encryption key is not configured",
                status_code=500,
            )

        previous_keys = []
        if isinstance(previous_keys_raw, list):
            previous_keys = [str(k).strip() for k in previous_keys_raw if k and str(k).strip()]
        elif isinstance(previous_keys_raw, str) and previous_keys_raw.strip():
            previous_keys = [k.strip() for k in previous_keys_raw.split(",") if k.strip()]

        try:
            primary_bytes = primary_key.encode("utf-8") if isinstance(primary_key, str) else primary_key
            primary_fernet = Fernet(primary_bytes)
            all_fernets = [primary_fernet]
            for prev_key in previous_keys:
                prev_bytes = prev_key.encode("utf-8") if isinstance(prev_key, str) else prev_key
                all_fernets.append(Fernet(prev_bytes))
            return primary_fernet, MultiFernet(all_fernets), str(key_version)
        except Exception:
            raise ProviderResolutionError(
                code=ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED,
                message="Provider encryption key configuration is invalid",
                status_code=500,
            )

    @classmethod
    def _cipher(cls):
        primary_fernet, _, _ = cls._get_fernet_instances()
        return primary_fernet

    @classmethod
    def _encrypt_credentials(cls, credentials_dict):
        primary_fernet, _, key_version = cls._get_fernet_instances()
        ciphertext = primary_fernet.encrypt(
            json.dumps(credentials_dict).encode("utf-8")
        ).decode("ascii")
        return ciphertext, key_version

    @classmethod
    def _decrypt_credentials(cls, ciphertext, provider=None, organization_id=None):
        if not ciphertext or not isinstance(ciphertext, str):
            raise ProviderResolutionError(
                code=ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED,
                message="Stored provider credentials could not be decrypted cleanly",
                status_code=500,
                provider=provider,
                organization_id=organization_id,
            )
        _, multi_fernet, _ = cls._get_fernet_instances()
        try:
            decrypted = multi_fernet.decrypt(ciphertext.strip().encode("utf-8"))
            parsed = json.loads(decrypted.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("Decrypted credentials payload is not an object")
            return parsed
        except (InvalidToken, Exception):
            raise ProviderResolutionError(
                code=ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED,
                message="Stored provider credentials could not be decrypted cleanly",
                status_code=500,
                provider=provider,
                organization_id=organization_id,
            )

    @classmethod
    def _is_document_active(cls, doc):
        if not doc:
            return False
        if doc.get("disconnected") is True:
            return False
        if doc.get("configured") is False:
            return False
        status = str(doc.get("status") or "").strip().upper()
        if status in cls.INACTIVE_STATUSES:
            return False
        return bool(doc.get("configured", False))

    @classmethod
    def validate_credentials(cls, provider, credentials):
        """Validate required credential structure for each provider."""
        if not provider or not isinstance(credentials, dict):
            raise ValueError("Provider name and credentials dictionary are required")

        provider = provider.lower().strip()

        if provider == "sendgrid":
            api_key = credentials.get("api_key")
            from_email = credentials.get("from_email")
            if not api_key or not isinstance(api_key, str) or not api_key.strip():
                raise ValueError("SendGrid requires a non-empty 'api_key'")
            if not from_email or not isinstance(from_email, str) or "@" not in from_email:
                raise ValueError("SendGrid requires a valid 'from_email'")

        elif provider in ("ses", "amazon_ses"):
            key = credentials.get("aws_access_key_id")
            secret = credentials.get("aws_secret_access_key")
            from_email = credentials.get("from_email")
            if not key or not str(key).strip():
                raise ValueError("Amazon SES requires 'aws_access_key_id'")
            if not secret or not str(secret).strip():
                raise ValueError("Amazon SES requires 'aws_secret_access_key'")
            if not from_email or not isinstance(from_email, str) or "@" not in from_email:
                raise ValueError("Amazon SES requires a valid 'from_email'")

        elif provider == "smtp":
            host = credentials.get("smtp_host")
            from_email = credentials.get("from_email")
            if not host or not str(host).strip():
                raise ValueError("SMTP requires 'smtp_host'")
            if not from_email or not isinstance(from_email, str) or "@" not in from_email:
                raise ValueError("SMTP requires a valid 'from_email'")

        elif provider == "twilio":
            account_sid = credentials.get("account_sid")
            auth_token = credentials.get("auth_token")
            from_number = credentials.get("from_number")
            messaging_service_sid = credentials.get("messaging_service_sid")

            if not account_sid or not isinstance(account_sid, str) or not account_sid.strip():
                raise ValueError("Twilio requires a non-empty 'account_sid'")
            if not auth_token or not isinstance(auth_token, str) or not auth_token.strip():
                raise ValueError("Twilio requires a non-empty 'auth_token'")
            if not from_number and not messaging_service_sid:
                raise ValueError("Twilio requires either 'from_number' or 'messaging_service_sid'")

        elif provider in ("meta", "whatsapp", "whatsapp_cloud"):
            access_token = credentials.get("access_token")
            phone_number_id = credentials.get("phone_number_id")

            if not access_token or not isinstance(access_token, str) or not access_token.strip():
                raise ValueError("WhatsApp Cloud API requires a non-empty 'access_token'")
            if not phone_number_id or not str(phone_number_id).strip():
                raise ValueError("WhatsApp Cloud API requires a non-empty 'phone_number_id'")

        elif provider in ("teams", "microsoft_teams", "msteams", "graph"):
            tenant_id = credentials.get("tenant_id")
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")
            access_token = credentials.get("access_token")

            if not access_token:
                if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
                    raise ValueError("Microsoft Teams requires a non-empty 'tenant_id'")
                if not client_id or not isinstance(client_id, str) or not client_id.strip():
                    raise ValueError("Microsoft Teams requires a non-empty 'client_id'")
                if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
                    raise ValueError("Microsoft Teams requires a non-empty 'client_secret'")

        elif provider == "mock":
            pass
        else:
            # For custom, plugin, or dynamic provider configurations, ensure credentials is not empty
            if not isinstance(credentials, dict) or not credentials:
                raise ValueError("Credentials dictionary cannot be empty")

        return True

    @classmethod
    def save_configuration(cls, provider, credentials, organization_id=None, active=True):

        provider = provider.lower().strip()
        if not isinstance(credentials, dict) or not credentials:
            raise ValueError("Credentials dictionary cannot be empty")

        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return None

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        query = {
            "provider": provider,
            "organization_id": organization_id
        }
        existing = collection.find_one(
            query,
            {"credentials": 1, "configured": 1, "disconnected": 1, "status": 1}
        )
        merged_credentials = {}
        if existing and existing.get("credentials") and existing.get("configured") is not False and not existing.get("disconnected"):
            merged_credentials = cls._decrypt_credentials(
                existing["credentials"],
                provider=provider,
                organization_id=organization_id,
            )
        merged_credentials.update(credentials)
        cls.validate_credentials(provider, merged_credentials)

        encrypted_credentials, key_version = cls._encrypt_credentials(merged_credentials)

        set_doc = {
            "provider": provider,
            "organization_id": organization_id,
            "credentials": encrypted_credentials,
            "key_version": key_version,
            "configured": bool(active),
            "disconnected": not bool(active),
            "status": "ACTIVE" if active else "INACTIVE",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if "token_expires_at" in merged_credentials and merged_credentials["token_expires_at"] is not None:
            try:
                set_doc["token_expires_at"] = float(merged_credentials["token_expires_at"])
            except (ValueError, TypeError):
                pass

        collection.update_one(
            query,
            {"$set": set_doc},
            upsert=True
        )

        return True

    @classmethod
    def set_configuration_active_state(cls, provider, is_active, organization_id=None):
        """Activate or deactivate an existing provider configuration without removing credentials."""
        provider = provider.lower().strip()
        collection = current_app.mongo_db["provider_configs"]
        query = {
            "provider": provider,
            "organization_id": organization_id,
        }
        existing = collection.find_one(query)
        if not existing or not existing.get("credentials"):
            raise ProviderResolutionError(
                code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                message=f"Provider configuration '{provider}' was not found",
                status_code=404,
                provider=provider,
                organization_id=organization_id,
            )
        collection.update_one(
            query,
            {
                "$set": {
                    "configured": bool(is_active),
                    "disconnected": not bool(is_active),
                    "status": "ACTIVE" if is_active else "INACTIVE",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return True

    @staticmethod
    def get_configuration_status(provider, organization_id=None, allow_platform_fallback=False):

        provider = provider.lower().strip()
        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return None

        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return None

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        projection = {
            "_id": 0,
            "provider": 1,
            "configured": 1,
            "disconnected": 1,
            "status": 1,
            "organization_id": 1,
            "updated_at": 1
        }

        doc = collection.find_one(
            {
                "provider": provider,
                "organization_id": organization_id
            },
            projection
        )

        if not doc and organization_id is not None and allow_platform_fallback:
            if PlatformProviderPolicy.is_authorized(organization_id, provider=provider):
                doc = collection.find_one(
                    {
                        "provider": provider,
                        "organization_id": None
                    },
                    projection
                )

        return doc

    @staticmethod
    def get_all_configuration_statuses(organization_id=None, include_all_tenants=False):
        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return []

        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return None

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        if organization_id is not None:
            query = {"organization_id": organization_id}
        elif include_all_tenants:
            query = {}
        else:
            query = {"organization_id": None}

        return list(
            collection.find(
                query,
                {
                    "_id": 0,
                    "provider": 1,
                    "configured": 1,
                    "disconnected": 1,
                    "status": 1,
                    "organization_id": 1,
                    "updated_at": 1
                }
            )
        )

    @classmethod
    def get_decrypted_configuration(
        cls,
        provider,
        organization_id=None,
        allow_platform_fallback=False,
        require_active=True,
    ):

        provider = provider.lower().strip()

        if organization_id is not None:
            if not isinstance(organization_id, str) or not organization_id.strip():
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                    message="Valid organization_id is required for tenant provider configuration lookup",
                    status_code=403,
                    provider=provider,
                )
            organization_id = organization_id.strip()

        if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
            return None

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        document = None

        # 1. Organization-specific configuration (strict tenant match)
        if organization_id is not None:
            document = collection.find_one({
                "provider": provider,
                "organization_id": organization_id,
            })
            if document and not cls._is_document_active(document):
                if require_active:
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.PROVIDER_INACTIVE,
                        message=f"Provider '{provider}' configuration is inactive or disconnected for this organization",
                        status_code=400,
                        provider=provider,
                        organization_id=organization_id,
                    )
                return None

        # 2. Explicit, authorized platform configuration lookup only
        if not document:
            if organization_id is None:
                document = collection.find_one({
                    "provider": provider,
                    "organization_id": None,
                })
                if document and not cls._is_document_active(document):
                    if require_active:
                        raise ProviderResolutionError(
                            code=ProviderResolutionError.PROVIDER_INACTIVE,
                            message=f"Platform provider '{provider}' configuration is inactive",
                            status_code=400,
                            provider=provider,
                        )
                    return None
            elif allow_platform_fallback:
                if not PlatformProviderPolicy.is_authorized(organization_id, provider=provider):
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                        message=f"Organization is not authorized to use platform credentials for provider '{provider}'",
                        status_code=403,
                        provider=provider,
                        organization_id=organization_id,
                    )
                document = collection.find_one({
                    "provider": provider,
                    "organization_id": None,
                })
                if document and not cls._is_document_active(document):
                    if require_active:
                        raise ProviderResolutionError(
                            code=ProviderResolutionError.PROVIDER_INACTIVE,
                            message=f"Authorized platform provider '{provider}' configuration is inactive",
                            status_code=400,
                            provider=provider,
                            organization_id=organization_id,
                        )
                    return None

        if not document:
            return None

        encrypted_credentials = document.get("credentials")
        if not encrypted_credentials:
            return None

        return cls._decrypt_credentials(
            encrypted_credentials,
            provider=provider,
            organization_id=organization_id,
        )

    @classmethod
    def get_teams_authorization_url(cls, organization_id, redirect_uri=None, user_id=None):
        """
        Generate Microsoft Entra ID OAuth 2.0 authorization URL
        for delegated Teams messaging consent (ChatMessage.Send, ChannelMessage.Send).
        Enforces RFC 7636 PKCE S256 and records a server-side OAuth transaction.
        """
        if not organization_id:
            raise ValueError("organization_id is required")

        existing = cls.get_decrypted_configuration("teams", organization_id=organization_id)
        if not existing:
            existing = cls.get_decrypted_configuration("microsoft_teams", organization_id=organization_id) or {}

        tenant_id = existing.get("tenant_id") or os.getenv("TEAMS_TENANT_ID") or os.getenv("AZURE_TENANT_ID") or "common"
        client_id = existing.get("client_id") or os.getenv("TEAMS_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
        resolved_redirect_uri = (
            redirect_uri
            or existing.get("redirect_uri")
            or os.getenv("TEAMS_REDIRECT_URI")
            or "https://api.senderx.io/api/v1/provider-config/teams/oauth/callback"
        )

        if not is_redirect_uri_allowed(resolved_redirect_uri):
            raise ValueError(f"Redirect URI '{resolved_redirect_uri}' is not permitted by security policy")

        if not client_id:
            raise ValueError(
                "Microsoft Teams client_id (Application ID) is required to generate authorization URL. "
                "Configure client_id via provider-config API or TEAMS_CLIENT_ID environment variable."
            )

        # RFC 7636 PKCE S256
        code_verifier, code_challenge = generate_pkce_pair()

        # OpenID Connect Nonce
        nonce = os.urandom(16).hex()

        secret_key = current_app.config.get("SECRET_KEY")
        state = generate_oauth_state(organization_id=organization_id, secret_key=secret_key)

        # Store server-side OAuth transaction with 15-minute expiration
        now = time.time()
        tx_record = {
            "state": state,
            "organization_id": organization_id,
            "user_id": user_id,
            "nonce": nonce,
            "code_verifier": code_verifier,
            "code_challenge": code_challenge,
            "redirect_uri": resolved_redirect_uri,
            "status": "PENDING",
            "created_at": now,
            "expires_at": now + 900  # 15 minutes TTL
        }
        if hasattr(current_app, "mongo_db") and current_app.mongo_db is not None:
            current_app.mongo_db["oauth_transactions"].insert_one(tx_record)

        auth_url = generate_authorization_url(
            tenant_id=tenant_id,
            client_id=client_id,
            redirect_uri=resolved_redirect_uri,
            state=state,
            code_challenge=code_challenge,
            nonce=nonce
        )

        return {
            "success": True,
            "authorization_url": auth_url,
            "state": state,
            "redirect_uri": resolved_redirect_uri,
            "scopes": TEAMS_DELEGATED_SCOPES
        }

    @classmethod
    def handle_teams_oauth_callback(cls, code, state, redirect_uri=None, jwks_client=None, signing_key=None):
        """
        Process Microsoft Entra ID authorization code callback.
        Validates state cryptographic integrity and organization binding,
        enforces single-use consumption against replay attacks,
        recovers the server-side PKCE code_verifier and expected nonce,
        cryptographically verifies OpenID Connect ID token if present,
        exchanges code for access & refresh tokens, and encrypts credentials.
        """
        if not code or not state:
            return {
                "success": False,
                "status_code": 400,
                "message": "Both 'code' and 'state' parameters are required"
            }

        # 1. State cryptographic verification (constant-time HMAC check)
        secret_key = current_app.config.get("SECRET_KEY")
        is_valid, state_org_id, err_msg = validate_oauth_state(state, secret_key=secret_key)
        if not is_valid or not state_org_id:
            return {
                "success": False,
                "status_code": 400,
                "message": err_msg or "Invalid OAuth state"
            }

        # 2. Server-side transaction recovery & replay prevention (Atomic find_one_and_update)
        org_id = state_org_id
        code_verifier = None
        server_redirect_uri = None
        expected_nonce = None

        if hasattr(current_app, "mongo_db") and current_app.mongo_db is not None:
            col = current_app.mongo_db["oauth_transactions"]
            now = time.time()
            tx = col.find_one_and_update(
                {
                    "state": state,
                    "status": "PENDING",
                    "expires_at": {"$gt": now}
                },
                {
                    "$set": {
                        "status": "CONSUMED",
                        "consumed_at": now
                    }
                }
            )

            if not tx:
                # Check if it was already used (replay attack)
                consumed_tx = col.find_one({"state": state, "status": "CONSUMED"})
                if consumed_tx:
                    return {
                        "success": False,
                        "status_code": 400,
                        "message": "OAuth state has already been used (replay detected)"
                    }
                # Check if it expired
                expired_tx = col.find_one({"state": state, "expires_at": {"$lte": now}})
                if expired_tx:
                    return {
                        "success": False,
                        "status_code": 400,
                        "message": "OAuth transaction has expired"
                    }
                return {
                    "success": False,
                    "status_code": 400,
                    "message": "Invalid or untrusted OAuth transaction"
                }

            # Recover bound organization strictly from server-side transaction
            org_id = tx.get("organization_id") or state_org_id
            code_verifier = tx.get("code_verifier")
            server_redirect_uri = tx.get("redirect_uri")
            expected_nonce = tx.get("nonce")

        # Validate redirect_uri if supplied by caller
        resolved_redirect_uri = server_redirect_uri or redirect_uri
        if redirect_uri and server_redirect_uri:
            if redirect_uri.strip().rstrip("/") != server_redirect_uri.strip().rstrip("/"):
                return {
                    "success": False,
                    "status_code": 400,
                    "message": "Redirect URI mismatch with original authorization request"
                }

        if resolved_redirect_uri and not is_redirect_uri_allowed(resolved_redirect_uri):
            return {
                "success": False,
                "status_code": 400,
                "message": f"Redirect URI '{resolved_redirect_uri}' is not permitted by security policy"
            }

        existing = cls.get_decrypted_configuration("teams", organization_id=org_id)
        if not existing:
            existing = cls.get_decrypted_configuration("microsoft_teams", organization_id=org_id) or {}

        tenant_id = existing.get("tenant_id") or os.getenv("TEAMS_TENANT_ID") or os.getenv("AZURE_TENANT_ID") or "common"
        client_id = existing.get("client_id") or os.getenv("TEAMS_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
        client_secret = existing.get("client_secret") or os.getenv("TEAMS_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
        effective_redirect_uri = (
            resolved_redirect_uri
            or existing.get("redirect_uri")
            or os.getenv("TEAMS_REDIRECT_URI")
            or "https://api.senderx.io/api/v1/provider-config/teams/oauth/callback"
        )

        if not client_id or not client_secret:
            return {
                "success": False,
                "status_code": 400,
                "message": "Microsoft Teams client_id and client_secret must be configured before exchanging tokens"
            }

        # Exchange code for tokens (with PKCE code_verifier)
        try:
            token_data = exchange_code_for_tokens(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                code=code,
                redirect_uri=effective_redirect_uri,
                code_verifier=code_verifier
            )
        except ProviderError as p_err:
            return {
                "success": False,
                "status_code": p_err.status_code,
                "message": p_err.message,
                "error_code": p_err.error_code
            }
        except Exception as exc:
            return {
                "success": False,
                "status_code": 400,
                "message": f"Token exchange failed: {str(exc)}"
            }

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))
        token_expires_at = time.time() + expires_in

        # Retrieve connected user profile
        user_profile = get_user_profile(access_token)
        connected_user = user_profile.get("userPrincipalName") or user_profile.get("mail") or "unknown_ms_user"

        # Cryptographically verify Microsoft OpenID Connect ID token if present
        id_token = token_data.get("id_token")
        token_tid = None
        if id_token:
            try:
                expected_tid = existing.get("tenant_id") if existing.get("tenant_id") not in ("common", "organizations", "consumers") else None
                claims = verify_microsoft_id_token(
                    id_token=id_token,
                    client_id=client_id,
                    expected_nonce=expected_nonce,
                    expected_tenant_id=expected_tid,
                    jwks_client=jwks_client,
                    signing_key=signing_key
                )
                token_tid = claims.get("tid")
                if not connected_user or connected_user == "unknown_ms_user":
                    connected_user = claims.get("preferred_username") or claims.get("email") or claims.get("upn") or connected_user
            except ValueError as val_err:
                err_str = str(val_err)
                status_code = 403 if "Tenant mismatch" in err_str else 400
                return {
                    "success": False,
                    "status_code": status_code,
                    "message": f"Microsoft ID token verification failed: {err_str}"
                }

        # Update and encrypt organization provider configuration
        updated_credentials = dict(existing)
        updated_credentials.update({
            "auth_mode": "delegated",
            "tenant_id": token_tid or tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": effective_redirect_uri,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
            "connected_user": connected_user,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "scopes": token_data.get("scope", "").split()
        })

        cls.save_configuration("teams", updated_credentials, organization_id=org_id)

        return {
            "success": True,
            "status_code": 200,
            "message": "Microsoft Teams connected successfully for organization",
            "organization_id": org_id,
            "connected_user": connected_user,
            "expires_in": expires_in
        }

    @classmethod
    def update_refreshed_tokens(cls, provider, new_tokens, organization_id=None):
        """
        Atomically persist rotated access and refresh tokens without overwriting newer credentials.
        Performs a conditional update query in MongoDB based on organization_id and token_expires_at.
        Updates access token, refresh token and expiration together while preserving Fernet encryption.
        Returns whether the atomic update succeeded.
        """
        provider = provider.lower().strip()
        collection = current_app.mongo_db["provider_configs"]

        # Fetch current document
        current_doc = collection.find_one({
            "provider": provider,
            "organization_id": organization_id
        })
        if not current_doc or not current_doc.get("credentials"):
            return False

        try:
            current_creds = cls._decrypt_credentials(
                current_doc["credentials"],
                provider=provider,
                organization_id=organization_id,
            )
        except Exception:
            return False

        current_exp = float(current_creds.get("token_expires_at") or 0.0)
        new_exp = float(new_tokens.get("token_expires_at") or 0.0)

        # In-memory pre-check against stale tokens
        if current_exp > new_exp:
            return False

        updated_creds = dict(current_creds)
        updated_creds["access_token"] = new_tokens["access_token"]
        if new_tokens.get("refresh_token"):
            updated_creds["refresh_token"] = new_tokens["refresh_token"]
        updated_creds["token_expires_at"] = new_exp
        updated_creds["refreshed_at"] = datetime.now(timezone.utc).isoformat()

        # Re-encrypt updated credentials using current primary key
        encrypted_credentials, key_version = cls._encrypt_credentials(updated_creds)

        # Atomic conditional update query in MongoDB:
        # 1. Matches provider and organization_id
        # 2. Conditions strictly on token_expires_at < new_exp (or unindexed / null)
        # 3. Ensures existing encrypted credentials have not mutated concurrently
        conditional_query = {
            "provider": provider,
            "organization_id": organization_id,
            "$or": [
                {"token_expires_at": {"$lt": new_exp}},
                {"token_expires_at": {"$exists": False}},
                {"token_expires_at": None}
            ]
        }
        if "credentials" in current_doc:
            conditional_query["credentials"] = current_doc["credentials"]

        now_iso = datetime.now(timezone.utc).isoformat()
        result = collection.update_one(
            conditional_query,
            {
                "$set": {
                    "credentials": encrypted_credentials,
                    "key_version": key_version,
                    "token_expires_at": new_exp,
                    "configured": True,
                    "disconnected": False,
                    "status": "ACTIVE",
                    "refreshed_at": now_iso
                }
            }
        )

        return bool(result.modified_count > 0)

    @classmethod
    def disconnect_provider(cls, provider, organization_id=None):
        """
        Disconnect a provider connection.
        Removes credentials and marks configured=False.
        """
        provider = provider.lower().strip()
        collection = current_app.mongo_db["provider_configs"]
        result = collection.update_one(
            {"provider": provider, "organization_id": organization_id},
            {
                "$set": {
                    "configured": False,
                    "disconnected": True,
                    "status": "DISCONNECTED",
                    "disconnected_at": datetime.now(timezone.utc).isoformat()
                },
                "$unset": {
                    "credentials": ""
                }
            }
        )
        return result.modified_count > 0 or result.matched_count > 0
