
import base64
import json
import os
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from flask import current_app

from app.adapters.base_adapter import ProviderError
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


class ProviderConfigService:

    @staticmethod
    def _cipher():

        key = current_app.config.get(
            "CREDENTIAL_ENCRYPTION_KEY"
        )

        if not key:
            raise ValueError(
                "Encryption key is not configured"
            )

        return Fernet(key.encode())

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
    def save_configuration(cls, provider, credentials, organization_id=None):

        provider = provider.lower().strip()
        cls.validate_credentials(provider, credentials)

        encrypted_credentials = cls._cipher().encrypt(
            json.dumps(credentials).encode()
        ).decode()

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        query = {
            "provider": provider,
            "organization_id": organization_id
        }

        set_doc = {
            "provider": provider,
            "organization_id": organization_id,
            "credentials": encrypted_credentials,
            "configured": True
        }
        if "token_expires_at" in credentials and credentials["token_expires_at"] is not None:
            try:
                set_doc["token_expires_at"] = float(credentials["token_expires_at"])
            except (ValueError, TypeError):
                pass

        collection.update_one(
            query,
            {"$set": set_doc},
            upsert=True
        )

        return True

    @staticmethod
    def get_configuration_status(provider, organization_id=None):

        provider = provider.lower().strip()

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        doc = collection.find_one(
            {
                "provider": provider,
                "organization_id": organization_id
            },
            {
                "_id": 0,
                "provider": 1,
                "configured": 1,
                "organization_id": 1
            }
        )

        if not doc and organization_id is not None:
            # Check platform fallback status
            doc = collection.find_one(
                {
                    "provider": provider,
                    "organization_id": None
                },
                {
                    "_id": 0,
                    "provider": 1,
                    "configured": 1,
                    "organization_id": 1
                }
            )

        return doc

    @staticmethod
    def get_all_configuration_statuses(organization_id=None):

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        query = {"organization_id": organization_id} if organization_id is not None else {}

        return list(
            collection.find(
                query,
                {
                    "_id": 0,
                    "provider": 1,
                    "configured": 1,
                    "organization_id": 1
                }
            )
        )

    @classmethod
    def get_decrypted_configuration(cls, provider, organization_id=None):

        provider = provider.lower().strip()

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        document = None

        # 1. Organization-specific configuration
        if organization_id is not None:
            document = collection.find_one({
                "provider": provider,
                "organization_id": organization_id,
                "configured": True
            })

        # 2. Platform-level fallback
        if not document:
            document = collection.find_one({
                "provider": provider,
                "organization_id": None,
                "configured": True
            })

        if not document:
            return None

        encrypted_credentials = document.get(
            "credentials"
        )

        if not encrypted_credentials:
            return None

        decrypted = cls._cipher().decrypt(
            encrypted_credentials.encode()
        )

        return json.loads(decrypted.decode())

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
            decrypted = cls._cipher().decrypt(current_doc["credentials"].encode())
            current_creds = json.loads(decrypted.decode())
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

        # Re-encrypt updated credentials
        encrypted_credentials = cls._cipher().encrypt(
            json.dumps(updated_creds).encode()
        ).decode()

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
                    "token_expires_at": new_exp,
                    "configured": True,
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
                    "disconnected_at": datetime.now(timezone.utc).isoformat()
                },
                "$unset": {
                    "credentials": ""
                }
            }
        )
        return result.modified_count > 0 or result.matched_count > 0
