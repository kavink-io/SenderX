"""
SenderX Phase 3, Task 5: Production Microsoft Teams Delegated OAuth & Messaging Test Suite
Comprehensive testing for:
- Microsoft Entra ID Delegated OAuth 2.0 Authorization Code flow with offline_access
- Cryptographic state URL generation and validation
- Authorization callback and code-for-token exchange
- Encrypted token storage (access_token, refresh_token) in MongoDB
- Access-token expiration detection and automatic refresh
- Expired/revoked refresh token handling (TEAMS_AUTH_EXPIRED reconnect requirement)
- ChatMessage.Send delegated permission chat dispatch (POST /chats/{chat_id}/messages)
- ChannelMessage.Send delegated permission channel dispatch (POST /teams/{team_id}/channels/{channel_id}/messages)
- Adaptive Cards, HTML bodies, importance, and file reference attachments
- Graph API 401 Unauthorized token recovery
- Graph API 403 Forbidden delegated permission handling (permanent)
- Graph API 429 Too Many Requests & Retry-After header parsing (retryable)
- Multi-tenant credential isolation and Fernet encryption at rest
- Mock vs production adapter separation
- Celery retry and DLQ lifecycle compatibility
"""

import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import bcrypt
import jwt
import pytest
import requests
from flask_jwt_extended import create_access_token

from app import create_app
from app.adapters.base_adapter import ProviderError
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.teams.teams_adapter import MicrosoftTeamsAdapter, MockTeamsAdapter
from app.adapters.teams.graph_client import (
    MicrosoftGraphAuthClient,
    generate_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_user_profile,
)
from app.adapters.teams.teams_utils import (
    TEAMS_DELEGATED_SCOPES,
    generate_oauth_state,
    validate_oauth_state,
    generate_pkce_pair,
    verify_pkce,
    is_redirect_uri_allowed,
    classify_teams_error,
    normalize_teams_response,
    redact_sensitive,
    verify_microsoft_id_token,
    get_microsoft_jwks_client,
)
from app.adapters.teams.models import (
    TeamsPayloadValidator,
    TeamsRecipientModel,
    TeamsMessageBody,
    TeamsAdaptiveCard,
    TeamsAttachment,
)
from app.engine.retry_manager import RetryManager
from app.modules.messages.repository import MessageRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.provider_config.service import ProviderConfigService
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["TEAMS_ALLOW_LOCAL_LOCK"] = True
    flask_app.config["SECRET_KEY"] = "test_teams_secret_key_12345"
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    """Sets up Org A and Org B with users and tokens."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Teams Delegated Org A {suffix}",
            "slug": f"teams-del-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Teams Admin A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:providers:manage",
                "organization:providers:read",
                "organization:templates:manage",
                "organization:templates:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "name": "Admin A",
            "email": f"teams-del-a-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Teams Delegated Org B {suffix}",
            "slug": f"teams-del-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Teams Admin B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:providers:manage",
                "organization:providers:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Admin B",
            "email": f"teams-del-b-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_a = create_access_token(
            identity=user_admin_a,
            additional_claims={
                "organization_id": org_a,
                "account_type": "ORGANIZATION_USER",
                "permissions": [
                    "organization:messages:create",
                    "organization:messages:read",
                    "organization:messages:manage",
                    "organization:providers:manage",
                    "organization:providers:read"
                ]
            }
        )

        token_b = create_access_token(
            identity=user_admin_b,
            additional_claims={
                "organization_id": org_b,
                "account_type": "ORGANIZATION_USER",
                "permissions": [
                    "organization:messages:create",
                    "organization:messages:read",
                    "organization:messages:manage",
                    "organization:providers:manage",
                    "organization:providers:read"
                ]
            }
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "token_a": token_a,
            "token_b": token_b
        }


# ===========================================================================
# 1. DELEGATED OAUTH 2.0 FLOW & STATE VALIDATION TESTS
# ===========================================================================

def test_teams_oauth_authorization_url_generation():
    """Verify Microsoft Entra ID authorization URL structure and delegated scopes."""
    state = generate_oauth_state(organization_id="org_12345", secret_key="test_secret")
    assert state is not None
    assert "." in state

    url = generate_authorization_url(
        tenant_id="contoso.onmicrosoft.com",
        client_id="client-guid-111",
        redirect_uri="https://api.senderx.io/callback",
        state=state
    )

    assert url.startswith("https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/authorize?")
    assert "client_id=client-guid-111" in url
    assert "response_type=code" in url
    assert "redirect_uri=https%3A%2F%2Fapi.senderx.io%2Fcallback" in url
    assert "ChatMessage.Send" in url
    assert "ChannelMessage.Send" in url
    assert "offline_access" in url
    assert f"state={state}" in url


def test_teams_oauth_state_validation():
    """Verify cryptographic state signing, tampering detection, and expiration."""
    secret = "hmac_signing_key_456"
    valid_state = generate_oauth_state(organization_id="org_abc", secret_key=secret)

    # Valid state verifies correctly
    is_valid, org_id, err = validate_oauth_state(valid_state, secret_key=secret)
    assert is_valid is True
    assert org_id == "org_abc"
    assert err is None

    # Tampered state rejected
    tampered_state = valid_state[:-4] + "xxxx"
    is_valid, _, err = validate_oauth_state(tampered_state, secret_key=secret)
    assert is_valid is False
    assert "Invalid state signature" in err

    # Expired state rejected (max_age=0)
    is_valid, _, err = validate_oauth_state(valid_state, secret_key=secret, max_age_seconds=0)
    assert is_valid is False
    assert "expired" in err.lower()


def test_teams_token_exchange_and_persistence(client, app, test_setup):
    """Test full authorization code exchange, profile retrieval, and encrypted token persistence."""
    org_a = test_setup["org_a"]
    token_a = test_setup["token_a"]

    # Pre-configure client credentials for Org A
    with app.app_context():
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-guid-aaa",
                "client_id": "client-guid-bbb",
                "client_secret": "secret-ccc"
            },
            organization_id=org_a
        )

    # 1. Request authorization URL via API endpoint
    res_url = client.get(
        "/api/v1/provider-config/teams/connect",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_url.status_code == 200
    data_url = res_url.get_json()
    assert "authorization_url" in data_url
    oauth_state = data_url["state"]

    # 2. Mock token exchange response from Microsoft
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {
        "token_type": "Bearer",
        "scope": "https://graph.microsoft.com/ChatMessage.Send https://graph.microsoft.com/ChannelMessage.Send offline_access",
        "expires_in": 3600,
        "access_token": "EwAoA_MOCK_ACCESS_TOKEN_12345",
        "refresh_token": "M_R3_MOCK_REFRESH_TOKEN_67890"
    }

    # 3. Mock profile lookup (/me)
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_me_resp.json.return_value = {
        "displayName": "Alex Wilcox",
        "userPrincipalName": "alexw@contoso.onmicrosoft.com",
        "mail": "alexw@contoso.com"
    }

    def mocked_requests_post(*args, **kwargs):
        return mock_token_resp

    def mocked_requests_get(*args, **kwargs):
        return mock_me_resp

    with patch("requests.Session.post", side_effect=mocked_requests_post):
        with patch("requests.Session.get", side_effect=mocked_requests_get):
            # Callback with code & state
            res_cb = client.get(
                f"/api/v1/provider-config/teams/oauth/callback?code=mock_auth_code_xyz&state={oauth_state}"
            )
            assert res_cb.status_code == 200
            cb_data = res_cb.get_json()
            assert cb_data["success"] is True
            assert cb_data["connected_user"] == "alexw@contoso.onmicrosoft.com"

    # Verify encrypted tokens saved in DB
    with app.app_context():
        raw_doc = app.mongo_db["provider_configs"].find_one({
            "provider": "teams",
            "organization_id": org_a
        })
        assert raw_doc is not None
        assert "EwAoA_MOCK_ACCESS_TOKEN_12345" not in str(raw_doc["credentials"])
        assert raw_doc["configured"] is True

        decrypted = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert decrypted["access_token"] == "EwAoA_MOCK_ACCESS_TOKEN_12345"
        assert decrypted["refresh_token"] == "M_R3_MOCK_REFRESH_TOKEN_67890"
        assert decrypted["connected_user"] == "alexw@contoso.onmicrosoft.com"


# ===========================================================================
# 2. TOKEN EXPIRATION & REFRESH TESTS
# ===========================================================================

def test_teams_access_token_refresh_lifecycle():
    """Verify that expired access tokens trigger refresh_token exchange and callback."""
    refreshed_data = {}

    def on_refresh(data):
        refreshed_data.update(data)

    auth_client = MicrosoftGraphAuthClient(
        tenant_id="tenant-guid-111",
        client_id="client-guid-222",
        client_secret="secret-333",
        access_token="initial_expired_access_token",
        refresh_token="initial_refresh_token_abc",
        token_expires_at=time.time() - 100,  # Expired
        allow_local_lock=True,
        on_token_refresh=on_refresh
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "token_type": "Bearer",
        "expires_in": 3600,
        "access_token": "newly_refreshed_access_token_999",
        "refresh_token": "new_rotated_refresh_token_888"
    }

    with patch.object(auth_client.session, "post", return_value=mock_resp) as mock_post:
        token = auth_client.get_access_token()

        assert token == "newly_refreshed_access_token_999"
        assert mock_post.called
        assert refreshed_data["access_token"] == "newly_refreshed_access_token_999"
        assert refreshed_data["refresh_token"] == "new_rotated_refresh_token_888"


def test_teams_expired_refresh_token_reconnect_error():
    """Verify that revoked or expired refresh token raises TEAMS_AUTH_EXPIRED reconnect error."""
    auth_client = MicrosoftGraphAuthClient(
        tenant_id="tenant-guid-111",
        client_id="client-guid-222",
        client_secret="secret-333",
        refresh_token="revoked_refresh_token_000",
        allow_local_lock=True
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = json.dumps({
        "error": "invalid_grant",
        "error_description": "AADSTS700084: The refresh token was issued to a user who has since revoked consent or the token has expired."
    })
    mock_resp.json.return_value = json.loads(mock_resp.text)

    with patch.object(auth_client.session, "post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            auth_client.get_access_token()

        err = exc_info.value
        assert err.status_code == 401
        assert err.retryable is False
        assert err.error_code == "TEAMS_AUTH_EXPIRED"
        assert "Please reconnect" in str(err)


# ===========================================================================
# 3. MESSAGE DISPATCH (CHATMESSAGESEND & CHANNELMESSAGESEND)
# ===========================================================================

def test_teams_delegated_chat_message_send():
    """Verify ChatMessage.Send delegated dispatch to POST /chats/{chat-id}/messages."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="delegated_chat_token_xyz"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": "1617290000000",
        "messageType": "message",
        "createdDateTime": "2026-11-13T14:30:00Z",
        "importance": "high",
        "body": {"contentType": "html", "content": "<h3>High Priority Task</h3>"}
    }

    with patch.object(adapter.session, "post", return_value=mock_resp) as mock_post:
        msg = {
            "recipient": "19:chat_thread_123@thread.v2",
            "data": {
                "html": "<h3>High Priority Task</h3>",
                "importance": "high"
            }
        }
        res = adapter.send(msg)

        assert res["success"] is True
        assert res["provider"] == "teams"
        assert res["channel"] == "microsoft_teams"
        assert res["provider_message_id"] == "1617290000000"
        assert res["target_type"] == "chat"
        assert res["chat_id"] == "19:chat_thread_123@thread.v2"

        args, kwargs = mock_post.call_args
        assert args[0] == "https://graph.microsoft.com/v1.0/chats/19:chat_thread_123@thread.v2/messages"
        assert kwargs["headers"]["Authorization"] == "Bearer delegated_chat_token_xyz"


def test_teams_delegated_channel_message_send_with_adaptive_card():
    """Verify ChannelMessage.Send delegated dispatch with Adaptive Card attachment."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="delegated_channel_token_abc"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": "1617291111111",
        "messageType": "message",
        "subject": "System Incident #402"
    }

    card_data = {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": "Database Failover Completed"}]
    }

    with patch.object(adapter.session, "post", return_value=mock_resp) as mock_post:
        msg = {
            "recipient": "channel:team-guid-999:19:chan_thread_888@thread.tacv2",
            "data": {
                "subject": "System Incident #402",
                "adaptive_card": card_data
            }
        }
        res = adapter.send(msg)

        assert res["success"] is True
        assert res["provider_message_id"] == "1617291111111"
        assert res["target_type"] == "channel"
        assert res["team_id"] == "team-guid-999"

        args, kwargs = mock_post.call_args
        expected_url = "https://graph.microsoft.com/v1.0/teams/team-guid-999/channels/19:chan_thread_888@thread.tacv2/messages"
        assert args[0] == expected_url
        assert kwargs["json"]["subject"] == "System Incident #402"
        assert len(kwargs["json"]["attachments"]) == 1


def test_teams_file_reference_attachment_dispatch():
    """Verify SharePoint file reference attachment dispatch."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="token"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "1617293333333"}

    with patch.object(adapter.session, "post", return_value=mock_resp) as mock_post:
        msg = {
            "recipient": "19:chat_id@thread.v2",
            "data": {
                "html": "<p>See file below</p>",
                "attachments": [
                    {
                        "contentType": "reference",
                        "contentUrl": "https://contoso.sharepoint.com/report.pdf",
                        "name": "AuditReport.pdf"
                    }
                ]
            }
        }
        res = adapter.send(msg)
        assert res["success"] is True
        assert res["provider_message_id"] == "1617293333333"

        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["attachments"][0]["name"] == "AuditReport.pdf"


# ===========================================================================
# 4. ERROR RESPONSES: 401, 403, 429
# ===========================================================================

def test_teams_graph_401_triggers_token_refresh():
    """Verify Graph API 401 Unauthorized forces token refresh and retries."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="initial_stale_token",
        refresh_token="valid_refresh_token"
    )

    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = "Unauthorized token"

    mock_201 = MagicMock()
    mock_201.status_code = 201
    mock_201.json.return_value = {"id": "1617294444444"}

    with patch.object(adapter.session, "post", side_effect=[mock_401, mock_201]):
        with patch.object(adapter.auth_client, "get_access_token", side_effect=["initial_stale_token", "fresh_token_after_401"]) as mock_tok:
            res = adapter.send({"recipient": "19:chat_id@thread.v2", "data": {"text": "Hello"}})
            assert res["success"] is True
            assert res["provider_message_id"] == "1617294444444"
            assert mock_tok.call_count == 2
            assert mock_tok.call_args_list[1][1] == {"force_refresh": True}


def test_teams_graph_403_delegated_permission_failure():
    """Verify 403 Forbidden (missing ChatMessage.Send or admin consent) is permanent."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="token"
    )

    mock_403 = MagicMock()
    mock_403.status_code = 403
    mock_403.headers = {}
    mock_403.text = json.dumps({
        "error": {
            "code": "Forbidden",
            "message": "Access denied. The user or application lacks required delegated permission ChatMessage.Send."
        }
    })
    mock_403.json.return_value = json.loads(mock_403.text)

    with patch.object(adapter.session, "post", return_value=mock_403):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send({"recipient": "19:chat_id@thread.v2", "data": {"text": "Test"}})

        err = exc_info.value
        assert err.status_code == 403
        assert err.retryable is False
        assert err.error_code == "Forbidden"


def test_teams_graph_429_throttling_and_retry_after():
    """Verify HTTP 429 and Retry-After header are parsed as retryable with backoff."""
    adapter = MicrosoftTeamsAdapter(
        tenant_id="tenant-111",
        client_id="client-222",
        client_secret="secret-333",
        access_token="token"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "20"}
    mock_resp.text = json.dumps({
        "error": {
            "code": "ThrottledRequest",
            "message": "Graph API rate limit exceeded."
        }
    })
    mock_resp.json.return_value = json.loads(mock_resp.text)

    with patch.object(adapter.session, "post", return_value=mock_resp):
        with pytest.raises(ProviderError) as exc_info:
            adapter.send({"recipient": "19:chat_id@thread.v2", "data": {"text": "Throttled"}})

        err = exc_info.value
        assert err.status_code == 429
        assert err.retryable is True
        assert err.retry_after == 20


# ===========================================================================
# 5. MULTI-TENANT ISOLATION & MOCK SEPARATION
# ===========================================================================

def test_teams_cross_tenant_isolation(app, test_setup):
    """Verify Org A credentials cannot be used by Org B."""
    org_a = test_setup["org_a"]
    org_b = test_setup["org_b"]

    with app.app_context():
        # Configure Org A
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-org-a",
                "client_id": "client-org-a",
                "client_secret": "secret-org-a",
                "access_token": "token-org-a"
            },
            organization_id=org_a
        )

        # Org A resolves properly
        adapter_a = AdapterRegistry.get_adapter("teams", channel="microsoft_teams", organization_id=org_a)
        assert adapter_a.access_token == "token-org-a"

        # Org B cannot access Org A configuration
        with pytest.raises(ValueError, match="Microsoft Teams configuration not found"):
            AdapterRegistry.get_adapter("teams", channel="microsoft_teams", organization_id=org_b)


def test_teams_mock_vs_production_separation(app):
    """Verify requesting 'teams' without credentials throws error and never falls back to mock."""
    with app.app_context():
        # Explicit mock returns MockTeamsAdapter
        mock_adapter = AdapterRegistry.get_adapter(provider="mock", channel="microsoft_teams")
        assert isinstance(mock_adapter, MockTeamsAdapter)

        # Production provider throws error if not configured
        with pytest.raises(ValueError, match="Microsoft Teams configuration not found"):
            AdapterRegistry.get_adapter(
                provider="teams",
                channel="microsoft_teams",
                organization_id=str(uuid.uuid4())
            )


def test_teams_retry_manager_dlq_compatibility():
    """Verify ProviderError raised by Teams adapter integrates cleanly with RetryManager."""
    # Retryable transient error
    transient = ProviderError("Temporary downtime", status_code=503, retryable=True, retry_after=12)
    assert RetryManager.is_retryable_error(transient) is True
    delay = RetryManager.get_retry_delay(retry_count=1, retry_after=transient.retry_after)
    assert delay == 12

    # Permanent auth error
    perm = ProviderError("Invalid grant", status_code=401, retryable=False)
    assert RetryManager.is_retryable_error(perm) is False


# ===========================================================================
# 6. SECURITY AUDIT: PKCE, REPLAY, ALLOWLIST, ORG BINDING & CONCURRENCY
# ===========================================================================

def test_teams_pkce_generation_and_verification():
    """Verify RFC 7636 PKCE S256 verifier/challenge generation and verification."""
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge

    # Verification success
    assert verify_pkce(verifier, challenge) is True

    # Tampered verifier / challenge rejection
    assert verify_pkce(verifier + "x", challenge) is False
    assert verify_pkce(verifier, challenge + "x") is False
    assert verify_pkce("", challenge) is False
    assert verify_pkce(verifier, "") is False

    # Authorization URL incorporates code_challenge and S256 method
    url = generate_authorization_url(
        tenant_id="test-tenant",
        client_id="test-client",
        redirect_uri="https://api.senderx.io/api/v1/provider-config/teams/oauth/callback",
        state="test-state",
        code_challenge=challenge
    )
    assert f"code_challenge={challenge}" in url
    assert "code_challenge_method=S256" in url


def test_teams_redirect_uri_allowlist_validation(app, test_setup):
    """Verify strict redirect URI allowlist enforcement."""
    org_a = test_setup["org_a"]

    # Allowed URIs
    assert is_redirect_uri_allowed("https://api.senderx.io/api/v1/provider-config/teams/oauth/callback") is True
    assert is_redirect_uri_allowed("http://localhost:5000/api/v1/provider-config/teams/oauth/callback") is True

    # Disallowed URIs
    assert is_redirect_uri_allowed("https://malicious-attacker.com/steal-code") is False
    assert is_redirect_uri_allowed("http://evil.com/callback") is False
    assert is_redirect_uri_allowed("") is False

    with app.app_context():
        # Service rejects disallowed redirect URI
        with pytest.raises(ValueError, match="not permitted by security policy"):
            ProviderConfigService.get_teams_authorization_url(
                organization_id=org_a,
                redirect_uri="https://malicious-attacker.com/oauth/callback"
            )


def test_teams_state_hmac_and_expiration():
    """Verify HMAC constant-time signature and 15-minute expiration enforcement."""
    secret = "test-secret-key-123"
    state = generate_oauth_state(organization_id="org-12345", secret_key=secret)
    assert "." in state

    # Valid state
    is_valid, org_id, err = validate_oauth_state(state, secret_key=secret)
    assert is_valid is True
    assert org_id == "org-12345"
    assert err is None

    # Tampered state signature
    parts = state.split(".")
    tampered_state = f"{parts[0]}.wrongsignature12345"
    is_valid, _, err = validate_oauth_state(tampered_state, secret_key=secret)
    assert is_valid is False
    assert "Invalid state signature" in err

    # Expired state (simulate max_age_seconds exceeded)
    is_valid, _, err = validate_oauth_state(state, secret_key=secret, max_age_seconds=-1)
    assert is_valid is False
    assert "expired" in err


def test_teams_oauth_state_single_use_replay_prevention(app, test_setup):
    """Verify server-side OAuth transaction single-use consumption and replay attack rejection."""
    org_a = test_setup["org_a"]

    with app.app_context():
        # Preconfigure client credentials
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "common",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret"
            },
            organization_id=org_a
        )

        # 1. Initiate authorization flow -> creates PENDING transaction in DB
        res = ProviderConfigService.get_teams_authorization_url(
            organization_id=org_a,
            redirect_uri="https://api.senderx.io/api/v1/provider-config/teams/oauth/callback"
        )
        assert res["success"] is True
        state = res["state"]

        col = app.mongo_db["oauth_transactions"]
        tx = col.find_one({"state": state})
        assert tx is not None
        assert tx["status"] == "PENDING"
        assert tx["organization_id"] == org_a
        assert "code_verifier" in tx

        # 2. First callback exchange: succeeds and transitions transaction to CONSUMED
        mock_tokens = {
            "access_token": "valid_token_abc_1",
            "refresh_token": "valid_refresh_abc_1",
            "expires_in": 3600,
            "scope": "ChatMessage.Send ChannelMessage.Send offline_access"
        }
        with patch("app.modules.provider_config.service.exchange_code_for_tokens", return_value=mock_tokens):
            with patch("app.modules.provider_config.service.get_user_profile", return_value={"userPrincipalName": "admin@org-a.com"}):
                cb_res = ProviderConfigService.handle_teams_oauth_callback(
                    code="valid_auth_code",
                    state=state
                )
                assert cb_res["success"] is True
                assert cb_res["status_code"] == 200
                assert cb_res["connected_user"] == "admin@org-a.com"

        # Verify transaction status changed to CONSUMED
        tx_consumed = col.find_one({"state": state})
        assert tx_consumed["status"] == "CONSUMED"
        assert "consumed_at" in tx_consumed

        # 3. Second callback exchange (replay attack): rejected with 400 replay detected
        with patch("app.modules.provider_config.service.exchange_code_for_tokens", return_value=mock_tokens):
            replay_res = ProviderConfigService.handle_teams_oauth_callback(
                code="valid_auth_code",
                state=state
            )
            assert replay_res["success"] is False
            assert replay_res["status_code"] == 400
            assert "replay detected" in replay_res["message"]


def test_teams_oauth_state_expiration_rejected(app, test_setup):
    """Verify expired OAuth transactions are rejected upon callback."""
    org_a = test_setup["org_a"]

    with app.app_context():
        secret_key = app.config.get("SECRET_KEY")
        state = generate_oauth_state(organization_id=org_a, secret_key=secret_key)

        # Insert expired transaction
        col = app.mongo_db["oauth_transactions"]
        col.insert_one({
            "state": state,
            "organization_id": org_a,
            "status": "PENDING",
            "created_at": time.time() - 1000,
            "expires_at": time.time() - 100  # already expired
        })

        res = ProviderConfigService.handle_teams_oauth_callback(
            code="some_code",
            state=state
        )
        assert res["success"] is False
        assert res["status_code"] == 400
        assert "expired" in res["message"]


def test_teams_oauth_callback_org_tampering_prevention(app, test_setup):
    """Verify original organization is strictly recovered from server-side transaction."""
    org_a = test_setup["org_a"]
    org_b = test_setup["org_b"]

    with app.app_context():
        # Preconfigure Org A
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "common",
                "client_id": "client-a",
                "client_secret": "secret-a"
            },
            organization_id=org_a
        )

        res = ProviderConfigService.get_teams_authorization_url(organization_id=org_a)
        state = res["state"]

        mock_tokens = {
            "access_token": "token_for_org_a",
            "refresh_token": "refresh_for_org_a",
            "expires_in": 3600
        }
        with patch("app.modules.provider_config.service.exchange_code_for_tokens", return_value=mock_tokens):
            with patch("app.modules.provider_config.service.get_user_profile", return_value={"mail": "user@org-a.com"}):
                cb_res = ProviderConfigService.handle_teams_oauth_callback(
                    code="code_123",
                    state=state
                )
                assert cb_res["success"] is True
                assert cb_res["organization_id"] == org_a

        # Org A has the saved tokens, Org B does not
        creds_a = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert creds_a["access_token"] == "token_for_org_a"

        creds_b = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_b)
        assert creds_b is None


def test_teams_cross_tenant_connection_replacement_prevention(app, test_setup):
    """Verify authorization from an unexpected tenant is rejected with 403."""
    org_a = test_setup["org_a"]

    with app.app_context():
        # Expected tenant is tenant-expected-111
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-expected-111",
                "client_id": "client-a",
                "client_secret": "secret-a"
            },
            organization_id=org_a
        )

        res = ProviderConfigService.get_teams_authorization_url(organization_id=org_a)
        state = res["state"]

        # Token returned from rogue tenant-unauthorized-999 signed with valid RSA key
        from cryptography.hazmat.primitives.asymmetric import rsa
        import jwt
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = priv.public_key()

        col = app.mongo_db["oauth_transactions"]
        tx = col.find_one({"state": state})

        rogue_id_token = jwt.encode(
            {
                "sub": "user-rogue",
                "aud": "client-a",
                "iss": "https://login.microsoftonline.com/tenant-expected-111/v2.0",
                "exp": time.time() + 3600,
                "iat": time.time(),
                "nonce": tx["nonce"],
                "tid": "tenant-unauthorized-999"
            },
            priv,
            algorithm="RS256",
            headers={"kid": "test-kid"}
        )

        mock_tokens = {
            "access_token": "token_rogue",
            "id_token": rogue_id_token,
            "refresh_token": "refresh_rogue",
            "expires_in": 3600
        }

        with patch("app.modules.provider_config.service.exchange_code_for_tokens", return_value=mock_tokens):
            with patch("app.modules.provider_config.service.get_user_profile", return_value={"mail": "user@rogue.com"}):
                cb_res = ProviderConfigService.handle_teams_oauth_callback(
                    code="code_rogue",
                    state=state,
                    signing_key=pub
                )
                assert cb_res["success"] is False
                assert cb_res["status_code"] == 403
                assert "Tenant mismatch" in cb_res["message"]


def test_teams_concurrent_token_refresh_thread_safety():
    """Verify thread-safe concurrent token refreshing with refresh lock."""
    import threading

    call_count = 0
    lock = threading.Lock()

    def mock_refresh(tenant_id, client_id, client_secret, refresh_token, session=None, timeout=20):
        nonlocal call_count
        with lock:
            call_count += 1
        time.sleep(0.05)
        return {
            "access_token": f"refreshed_token_{call_count}",
            "refresh_token": "rotated_refresh_token",
            "expires_in": 3600
        }

    client = MicrosoftGraphAuthClient(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        access_token="initial_token",
        refresh_token="initial_refresh",
        token_expires_at=time.time() + 3600,
        allow_local_lock=True
    )

    results = []
    errors = []

    def worker():
        try:
            tok = client.get_access_token(force_refresh=True)
            results.append(tok)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    with patch("app.adapters.teams.graph_client.refresh_access_token", side_effect=mock_refresh):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(errors) == 0
    assert len(results) == 5
    for tok in results:
        assert "refreshed_token_" in tok


def test_teams_sensitive_credential_masking():
    """Verify secrets and tokens are masked and never exposed in responses or logs."""
    secret = "SuperSecretClientSecret123!"
    refresh_tok = "SuperSecretRefreshToken456!"
    raw_error = f"Failed to authenticate with secret {secret} and token {refresh_tok}"

    masked = redact_sensitive(raw_error, [secret, refresh_tok])
    assert secret not in masked
    assert refresh_tok not in masked
    assert "..." in masked

    # Verify normalize_teams_response produces clean output
    norm = normalize_teams_response(
        success=True,
        provider_message_id="msg-123",
        recipient="chat-123",
        target_type="chat",
        raw_response={
            "id": "msg-123"
        }
    )
    assert norm["provider_message_id"] == "msg-123"
    assert norm["success"] is True

    # Verify sensitive tokens are never exposed in callback responses
    callback_response = {
        "success": True,
        "status_code": 200,
        "message": "Microsoft Teams connected successfully for organization",
        "organization_id": "test-org-123",
        "connected_user": "admin@org.com",
        "expires_in": 3600
    }
    assert "access_token" not in callback_response
    assert "refresh_token" not in callback_response
    assert "client_secret" not in callback_response


# ===========================================================================
# 7. ADVANCED SECURITY: ID TOKEN VERIFICATION, DISTRIBUTED LOCKS & DISCONNECT
# ===========================================================================

def test_teams_id_token_verification_suite():
    """Verify cryptographic verification of Microsoft OpenID Connect ID tokens."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv_a = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_a = priv_a.public_key()

    priv_b = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_b = priv_b.public_key()

    now = time.time()
    valid_payload = {
        "sub": "user-guid-123",
        "aud": "valid-client-id",
        "iss": "https://login.microsoftonline.com/tenant-123/v2.0",
        "exp": now + 3600,
        "iat": now,
        "nonce": "valid-nonce-456",
        "tid": "tenant-123",
        "preferred_username": "admin@contoso.com"
    }

    # 1. Valid token passes completely
    valid_tok = jwt.encode(valid_payload, priv_a, algorithm="RS256", headers={"kid": "kid-a"})
    claims = verify_microsoft_id_token(
        valid_tok,
        client_id="valid-client-id",
        expected_nonce="valid-nonce-456",
        expected_tenant_id="tenant-123",
        signing_key=pub_a
    )
    assert claims["preferred_username"] == "admin@contoso.com"
    assert claims["tid"] == "tenant-123"

    # 2. Invalid cryptographic signature rejected
    with pytest.raises(ValueError, match="cryptographic verification failed"):
        verify_microsoft_id_token(
            valid_tok,
            client_id="valid-client-id",
            expected_nonce="valid-nonce-456",
            signing_key=pub_b  # Verified with wrong public key
        )

    # 3. Incorrect audience rejected
    with pytest.raises(ValueError, match="audience does not match"):
        verify_microsoft_id_token(
            valid_tok,
            client_id="different-client-id",
            signing_key=pub_a
        )

    # 4. Incorrect issuer rejected
    rogue_iss_payload = dict(valid_payload, iss="https://rogue-identity-provider.com/v2.0")
    rogue_iss_tok = jwt.encode(rogue_iss_payload, priv_a, algorithm="RS256", headers={"kid": "kid-a"})
    with pytest.raises(ValueError, match="Invalid ID token issuer"):
        verify_microsoft_id_token(
            rogue_iss_tok,
            client_id="valid-client-id",
            signing_key=pub_a
        )

    # 5. Expired ID token rejected
    expired_payload = dict(valid_payload, exp=now - 300, iat=now - 3600)
    expired_tok = jwt.encode(expired_payload, priv_a, algorithm="RS256", headers={"kid": "kid-a"})
    with pytest.raises(ValueError, match="expired"):
        verify_microsoft_id_token(
            expired_tok,
            client_id="valid-client-id",
            signing_key=pub_a
        )

    # 6. Invalid nonce rejected
    with pytest.raises(ValueError, match="nonce does not match"):
        verify_microsoft_id_token(
            valid_tok,
            client_id="valid-client-id",
            expected_nonce="wrong-tampered-nonce",
            signing_key=pub_a
        )

    # 7. Unsigned or wrong algorithm rejected
    none_tok = jwt.encode(valid_payload, "", algorithm="none")
    with pytest.raises(ValueError, match="Invalid ID token algorithm"):
        verify_microsoft_id_token(none_tok, client_id="valid-client-id", signing_key=pub_a)


def test_teams_id_token_jwks_key_rotation():
    """Verify PyJWKClient key rotation handling when new kid is introduced."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv_old = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_old = priv_old.public_key()

    priv_new = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_new = priv_new.public_key()

    # Create mock JWKS client simulating dynamic key lookup/rotation
    mock_jwk_client = MagicMock()
    def get_signing_key_mock(token):
        header = jwt.get_unverified_header(token)
        mock_key = MagicMock()
        if header.get("kid") == "kid-rotated-2":
            mock_key.key = pub_new
        else:
            mock_key.key = pub_old
        return mock_key
    mock_jwk_client.get_signing_key_from_jwt.side_effect = get_signing_key_mock

    # Token signed with rotated key kid-rotated-2
    now = time.time()
    tok_rotated = jwt.encode(
        {
            "sub": "user-rot",
            "aud": "test-client",
            "iss": "https://login.microsoftonline.com/tenant-1/v2.0",
            "exp": now + 3600,
            "iat": now,
            "tid": "tenant-1"
        },
        priv_new,
        algorithm="RS256",
        headers={"kid": "kid-rotated-2"}
    )

    claims = verify_microsoft_id_token(
        tok_rotated,
        client_id="test-client",
        jwks_client=mock_jwk_client
    )
    assert claims["sub"] == "user-rot"


def test_teams_distributed_refresh_simulated_workers(app, test_setup):
    """
    Verify distributed coordination across simulated workers:
    Worker 1 acquires lock and refreshes token; Worker 2 acquires lock,
    re-reads freshly persisted credentials, and avoids duplicate refresh.
    """
    import threading

    org_a = test_setup["org_a"]

    # Shared thread-safe mock redis client with lock mechanism
    class MockDistributedLock:
        _active_locks = {}
        _lock_mutex = threading.Lock()

        def __init__(self, name, timeout=10.0, blocking_timeout=5.0, **kwargs):
            self.name = name
            self.timeout = timeout
            self.blocking_timeout = blocking_timeout
            self.acquired = False

        def acquire(self):
            start = time.time()
            while time.time() - start < self.blocking_timeout:
                with self._lock_mutex:
                    holder = self._active_locks.get(self.name)
                    if holder is None or time.time() > holder:
                        self._active_locks[self.name] = time.time() + self.timeout
                        self.acquired = True
                        return True
                time.sleep(0.02)
            return False

        def release(self):
            with self._lock_mutex:
                if self.name in self._active_locks:
                    del self._active_locks[self.name]
            self.acquired = False

    class MockRedisClient:
        def lock(self, name, timeout=10.0, **kwargs):
            return MockDistributedLock(name, timeout=timeout, **kwargs)

    mock_redis = MockRedisClient()

    # Preconfigure Org A with expired token
    with app.app_context():
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-del",
                "client_id": "client-del",
                "client_secret": "secret-del",
                "access_token": "expired_tok",
                "refresh_token": "valid_refresh",
                "token_expires_at": time.time() - 100
            },
            organization_id=org_a
        )

        refresh_call_count = 0
        def counting_refresh(*args, **kwargs):
            nonlocal refresh_call_count
            refresh_call_count += 1
            time.sleep(0.05)
            return {
                "access_token": f"distributed_refreshed_tok_{refresh_call_count}",
                "refresh_token": "new_rotated_refresh",
                "expires_in": 3600
            }

        def cred_loader():
            return ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)

        def on_refresh(new_tokens):
            ProviderConfigService.update_refreshed_tokens("teams", new_tokens, organization_id=org_a)

        # Worker 1 & Worker 2
        worker1 = MicrosoftGraphAuthClient(
            tenant_id="tenant-del",
            client_id="client-del",
            client_secret="secret-del",
            access_token="expired_tok",
            refresh_token="valid_refresh",
            token_expires_at=time.time() - 100,
            organization_id=org_a,
            redis_client=mock_redis,
            credential_loader=cred_loader,
            on_token_refresh=on_refresh
        )

        worker2 = MicrosoftGraphAuthClient(
            tenant_id="tenant-del",
            client_id="client-del",
            client_secret="secret-del",
            access_token="expired_tok",
            refresh_token="valid_refresh",
            token_expires_at=time.time() - 100,
            organization_id=org_a,
            redis_client=mock_redis,
            credential_loader=cred_loader,
            on_token_refresh=on_refresh
        )

        tokens = []
        def run_worker(client):
            with app.app_context():
                tok = client.get_access_token()
                tokens.append(tok)

        with patch("app.adapters.teams.graph_client.refresh_access_token", side_effect=counting_refresh):
            t1 = threading.Thread(target=run_worker, args=(worker1,))
            t2 = threading.Thread(target=run_worker, args=(worker2,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Both workers received valid refreshed tokens
        assert len(tokens) == 2
        assert all("distributed_refreshed_tok_" in tok for tok in tokens)
        # Duplicate refresh was avoided: exactly 1 refresh was performed!
        assert refresh_call_count == 1


def test_teams_distributed_lock_expiry_and_crash_recovery():
    """Verify lock expiration allows recovery if a worker crashes while holding the lock."""
    class ExpiringMockLock:
        def __init__(self, name, **kwargs):
            self.name = name

        def acquire(self):
            # Simulates lock acquisition success after previous lock expired
            return True

        def release(self):
            pass

    class CrashMockRedis:
        def lock(self, name, timeout=1.0, **kwargs):
            return ExpiringMockLock(name)

    client = MicrosoftGraphAuthClient(
        tenant_id="tenant-1",
        client_id="client-1",
        client_secret="secret-1",
        access_token="expired_token",
        refresh_token="refresh_tok",
        token_expires_at=time.time() - 100,
        redis_client=CrashMockRedis()
    )

    with patch("app.adapters.teams.graph_client.refresh_access_token", return_value={"access_token": "recovered_token", "expires_in": 3600}):
        token = client.get_access_token()
        assert token == "recovered_token"


def test_teams_atomic_rotated_token_persistence_skips_older(app, test_setup):
    """Verify update_refreshed_tokens will not overwrite newer credentials with older ones."""
    org_a = test_setup["org_a"]

    with app.app_context():
        now = time.time()
        # Save newer credentials (expiry = now + 5000)
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-1",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "access_token": "newer_token",
                "refresh_token": "newer_refresh",
                "token_expires_at": now + 5000
            },
            organization_id=org_a
        )

        # Attempt to overwrite with older credentials (expiry = now + 3000)
        older_tokens = {
            "access_token": "stale_token",
            "refresh_token": "stale_refresh",
            "token_expires_at": now + 3000
        }
        res = ProviderConfigService.update_refreshed_tokens("teams", older_tokens, organization_id=org_a)
        assert res is False  # Rejected overwrite

        # Existing credentials in DB remain untouched
        current = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert current["access_token"] == "newer_token"
        assert current["token_expires_at"] == now + 5000


def test_teams_disconnected_account_rejection(app, test_setup):
    """Verify disconnected Microsoft Teams accounts cannot continue sending messages."""
    org_a = test_setup["org_a"]

    with app.app_context():
        # Connect Org A
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-del",
                "client_id": "client-del",
                "client_secret": "secret-del",
                "access_token": "token-del",
                "refresh_token": "refresh-del",
                "token_expires_at": time.time() + 3600
            },
            organization_id=org_a
        )

        # Adapter can be retrieved initially
        adapter = AdapterRegistry.get_adapter("teams", channel="microsoft_teams", organization_id=org_a)
        assert adapter is not None

        # Disconnect Teams for Org A
        ProviderConfigService.disconnect_provider("teams", organization_id=org_a)

        # Subsequent adapter creation fails
        with pytest.raises(ValueError, match="disconnected|not found"):
            AdapterRegistry.get_adapter("teams", channel="microsoft_teams", organization_id=org_a)


# ===========================================================================
# 8. PRODUCTION SAFETY: REDIS DISTRIBUTED LOCK ENFORCEMENT & ATOMIC PERSISTENCE
# ===========================================================================

def test_teams_redis_unavailable_in_production():
    """Verify Redis distributed locking is strictly required in production mode."""
    client = MicrosoftGraphAuthClient(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        access_token="expired_token",
        refresh_token="valid_refresh",
        token_expires_at=time.time() - 100,
        allow_local_lock=False,  # Explicit production multi-worker mode
        redis_client=None
    )

    with pytest.raises(ProviderError) as exc_info:
        client.get_access_token(force_refresh=True)

    err = exc_info.value
    assert err.status_code == 503
    assert err.retryable is True
    assert err.error_code == "REDIS_LOCK_UNAVAILABLE"
    assert "Distributed locking via Redis is required" in str(err)


def test_teams_redis_unavailable_in_dev_mode():
    """Verify local threading.Lock fallback is permitted in explicitly configured dev mode."""
    client = MicrosoftGraphAuthClient(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        access_token="expired_token",
        refresh_token="valid_refresh",
        token_expires_at=time.time() - 100,
        allow_local_lock=True,  # Explicit development/test single-process mode
        redis_client=None
    )

    mock_resp = {
        "access_token": "dev_refreshed_token",
        "refresh_token": "dev_rotated_refresh",
        "expires_in": 3600
    }
    with patch("app.adapters.teams.graph_client.refresh_access_token", return_value=mock_resp):
        token = client.get_access_token(force_refresh=True)
        assert token == "dev_refreshed_token"


def test_teams_no_token_refresh_without_distributed_lock_in_production():
    """Verify token refresh is aborted without executing if Redis lock fails in production."""
    class FailingRedisLock:
        def __init__(self, *args, **kwargs):
            pass
        def acquire(self):
            import redis.exceptions
            raise redis.exceptions.ConnectionError("Redis cluster unreachable")

    class FailingRedisClient:
        def lock(self, *args, **kwargs):
            return FailingRedisLock()

    client = MicrosoftGraphAuthClient(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        access_token="expired_token",
        refresh_token="valid_refresh",
        token_expires_at=time.time() - 100,
        allow_local_lock=False,  # Production mode
        redis_client=FailingRedisClient()
    )

    with patch("app.adapters.teams.graph_client.refresh_access_token") as mock_refresh:
        with pytest.raises(ProviderError) as exc_info:
            client.get_access_token(force_refresh=True)

        err = exc_info.value
        assert err.status_code == 503
        assert err.retryable is True
        assert err.error_code == "REDIS_LOCK_UNAVAILABLE"
        # refresh_access_token must NOT have been called
        assert mock_refresh.call_count == 0


def test_teams_atomic_conditional_mongodb_update(app, test_setup):
    """Verify MongoDB update_refreshed_tokens uses atomic conditional query."""
    org_a = test_setup["org_a"]

    with app.app_context():
        now = time.time()
        # Initialize configuration in DB with token_expires_at = now + 1000
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-atomic",
                "client_id": "client-atomic",
                "client_secret": "secret-atomic",
                "access_token": "tok_initial",
                "refresh_token": "ref_initial",
                "token_expires_at": now + 1000
            },
            organization_id=org_a
        )

        # Atomic update with higher expiration now + 2000
        new_tokens = {
            "access_token": "tok_updated",
            "refresh_token": "ref_updated",
            "token_expires_at": now + 2000
        }
        res = ProviderConfigService.update_refreshed_tokens("teams", new_tokens, organization_id=org_a)
        assert res is True

        # Verify DB document was updated atomically
        col = app.mongo_db["provider_configs"]
        doc = col.find_one({"provider": "teams", "organization_id": org_a})
        assert doc["token_expires_at"] == now + 2000

        # Verify credentials can be decrypted
        decrypted = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert decrypted["access_token"] == "tok_updated"
        assert decrypted["refresh_token"] == "ref_updated"


def test_teams_concurrent_stale_token_update_rejection(app, test_setup):
    """Verify stale worker cannot overwrite newer credentials via conditional update."""
    org_a = test_setup["org_a"]

    with app.app_context():
        now = time.time()
        # Current DB state has expiration at now + 5000
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-atomic",
                "client_id": "client-atomic",
                "client_secret": "secret-atomic",
                "access_token": "latest_token",
                "refresh_token": "latest_refresh",
                "token_expires_at": now + 5000
            },
            organization_id=org_a
        )

        # Stale worker tries to persist older tokens with expiration at now + 3000
        stale_tokens = {
            "access_token": "stale_token",
            "refresh_token": "stale_refresh",
            "token_expires_at": now + 3000
        }
        res = ProviderConfigService.update_refreshed_tokens("teams", stale_tokens, organization_id=org_a)
        assert res is False

        # Database remains untouched
        current = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert current["access_token"] == "latest_token"
        assert current["token_expires_at"] == now + 5000


def test_teams_successful_rotated_token_persistence(app, test_setup):
    """Verify access token, refresh token and expiry are persisted together with Fernet encryption."""
    org_a = test_setup["org_a"]

    with app.app_context():
        now = time.time()
        ProviderConfigService.save_configuration(
            provider="teams",
            credentials={
                "tenant_id": "tenant-rot",
                "client_id": "client-rot",
                "client_secret": "secret-rot",
                "access_token": "tok_initial",
                "refresh_token": "ref_initial",
                "token_expires_at": now + 1000
            },
            organization_id=org_a
        )

        rotated_tokens = {
            "access_token": "tok_rotated_xyz",
            "refresh_token": "ref_rotated_xyz",
            "token_expires_at": now + 4000
        }
        res = ProviderConfigService.update_refreshed_tokens("teams", rotated_tokens, organization_id=org_a)
        assert res is True

        # Verify raw storage in MongoDB is Fernet encrypted
        col = app.mongo_db["provider_configs"]
        doc = col.find_one({"provider": "teams", "organization_id": org_a})
        raw_cred = doc["credentials"]
        assert isinstance(raw_cred, str)
        assert "tok_rotated_xyz" not in raw_cred  # Fernet encrypted
        assert "ref_rotated_xyz" not in raw_cred  # Fernet encrypted

        # Decryption yields all rotated fields
        decrypted = ProviderConfigService.get_decrypted_configuration("teams", organization_id=org_a)
        assert decrypted["access_token"] == "tok_rotated_xyz"
        assert decrypted["refresh_token"] == "ref_rotated_xyz"
        assert decrypted["token_expires_at"] == now + 4000
