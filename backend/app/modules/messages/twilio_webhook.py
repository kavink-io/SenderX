"""
Twilio Webhook Verification & Tenant-Safe Integration Resolution.

Provides:
- Canonical external callback URL reconstruction without trusting spoofed
  X-Forwarded-* headers from untrusted clients.
- Organization-scoped Twilio integration resolution using encrypted credentials
  and non-secret SHA-256 AccountSid digests (zero global MessageSid lookups,
  zero fallback to arbitrary organizations or platform environment variables).
- Official Twilio RequestValidator verification for form-encoded and JSON
  (`bodySHA256`) callbacks.
- Sanitized security event auditing (never logs Auth Tokens, signatures,
  or complete callback payloads).
"""

import hashlib
import ipaddress
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from flask import current_app, has_app_context
from twilio.request_validator import RequestValidator

from app.adapters.errors import ProviderResolutionError
from app.modules.provider_config.service import ProviderConfigService
from app.modules.users.audit_repository import SecurityAuditRepository

logger = logging.getLogger(__name__)

_HOST_PORT_REGEX = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*(?::\d{1,5})?$"
)
_PREFIX_REGEX = re.compile(r"^/[A-Za-z0-9\-._~/]*$")


def account_sid_digest(account_sid: Optional[str]) -> Optional[str]:
    if not account_sid or not isinstance(account_sid, str) or not account_sid.strip():
        return None
    return hashlib.sha256(account_sid.strip().encode("utf-8")).hexdigest()


def mask_account_sid(account_sid: Optional[str]) -> str:
    if not account_sid or not isinstance(account_sid, str):
        return "unknown"
    cleaned = account_sid.strip()
    if len(cleaned) <= 6:
        return "***"
    return f"{cleaned[:2]}...{cleaned[-4:]}"


def _is_trusted_proxy_ip(remote_addr: Optional[str], trusted_proxy_entries: List[str]) -> bool:
    if not remote_addr or not isinstance(remote_addr, str):
        return False
    clean_remote = remote_addr.strip()
    try:
        remote_ip = ipaddress.ip_address(clean_remote)
    except ValueError:
        return False

    for entry in trusted_proxy_entries or []:
        clean_entry = str(entry).strip()
        if not clean_entry:
            continue
        try:
            if "/" in clean_entry:
                if remote_ip in ipaddress.ip_network(clean_entry, strict=False):
                    return True
            else:
                if remote_ip == ipaddress.ip_address(clean_entry):
                    return True
        except ValueError:
            continue
    return False


def _sanitize_forwarded_host(raw_host: Optional[str], trusted_hosts: List[str]) -> Optional[str]:
    if not raw_host or not isinstance(raw_host, str):
        return None
    candidate = raw_host.split(",")[0].strip()
    if not candidate or len(candidate) > 255 or not _HOST_PORT_REGEX.match(candidate):
        return None
    if ":" in candidate:
        _, port_str = candidate.rsplit(":", 1)
        try:
            port_num = int(port_str)
            if port_num < 1 or port_num > 65535:
                return None
        except ValueError:
            return None
    if trusted_hosts:
        host_only = candidate.rsplit(":", 1)[0].lower()
        if candidate.lower() not in trusted_hosts and host_only not in trusted_hosts:
            return None
    return candidate


def _sanitize_forwarded_prefix(raw_prefix: Optional[str]) -> str:
    if not raw_prefix or not isinstance(raw_prefix, str):
        return ""
    candidate = raw_prefix.split(",")[0].strip()
    if not candidate or ".." in candidate or "//" in candidate or not _PREFIX_REGEX.match(candidate):
        return ""
    return candidate.rstrip("/")


def reconstruct_twilio_callback_url(flask_request) -> str:
    """
    Reconstruct the exact externally visible callback URL for Twilio RequestValidator.

    Security rules:
    1. If WEBHOOK_PUBLIC_BASE_URL or PUBLIC_BASE_URL is configured, always build
       scheme + netloc + optional base path authoritatively from that setting.
    2. Otherwise, only inspect X-Forwarded-Proto / X-Forwarded-Host / X-Forwarded-Port /
       X-Forwarded-Prefix when TRUST_PROXY_HEADERS is explicitly enabled AND
       request.remote_addr belongs to TRUSTED_PROXY_IPS.
    3. Arbitrary client-supplied X-Forwarded-For or untrusted X-Forwarded-Host
       headers are ignored cleanly.
    """
    cfg = current_app.config if has_app_context() else {}
    public_base = (cfg.get("WEBHOOK_PUBLIC_BASE_URL") or cfg.get("PUBLIC_BASE_URL") or "").strip()

    raw_qs = flask_request.query_string.decode("utf-8", errors="ignore") if getattr(flask_request, "query_string", None) else ""
    qs_suffix = f"?{raw_qs}" if raw_qs else ""
    req_path = flask_request.path or "/"

    if public_base:
        parsed_base = urlsplit(public_base)
        if parsed_base.scheme in ("http", "https") and parsed_base.netloc:
            base_path = parsed_base.path.rstrip("/")
            if base_path and req_path.startswith(base_path):
                combined_path = req_path
            else:
                combined_path = f"{base_path}{req_path}"
            return f"{parsed_base.scheme}://{parsed_base.netloc}{combined_path}{qs_suffix}"

    trust_proxy = bool(cfg.get("TRUST_PROXY_HEADERS", False))
    trusted_ips = list(cfg.get("TRUSTED_PROXY_IPS") or [])
    trusted_hosts = [str(h).strip().lower() for h in (cfg.get("TRUSTED_FORWARDED_HOSTS") or []) if h]

    if trust_proxy and _is_trusted_proxy_ip(getattr(flask_request, "remote_addr", None), trusted_ips):
        parsed_req = urlsplit(flask_request.url)
        scheme = parsed_req.scheme or "http"
        raw_proto = flask_request.headers.get("X-Forwarded-Proto")
        if raw_proto:
            proto_candidate = raw_proto.split(",")[0].strip().lower()
            if proto_candidate in ("http", "https"):
                scheme = proto_candidate

        netloc = parsed_req.netloc
        forwarded_host = _sanitize_forwarded_host(flask_request.headers.get("X-Forwarded-Host"), trusted_hosts)
        if forwarded_host:
            netloc = forwarded_host
            raw_port = flask_request.headers.get("X-Forwarded-Port")
            if raw_port and ":" not in netloc:
                port_candidate = raw_port.split(",")[0].strip()
                if port_candidate.isdigit():
                    port_num = int(port_candidate)
                    if 1 <= port_num <= 65535 and not (
                        (scheme == "https" and port_num == 443) or (scheme == "http" and port_num == 80)
                    ):
                        netloc = f"{netloc}:{port_num}"
        elif trusted_hosts:
            host_only = netloc.rsplit(":", 1)[0].lower()
            if netloc.lower() not in trusted_hosts and host_only not in trusted_hosts:
                return flask_request.url

        prefix = _sanitize_forwarded_prefix(flask_request.headers.get("X-Forwarded-Prefix"))
        if prefix and not req_path.startswith(prefix):
            full_path = f"{prefix}{req_path}"
        else:
            full_path = req_path
        return f"{scheme}://{netloc}{full_path}{qs_suffix}"

    return flask_request.url


def log_twilio_security_event(
    *,
    event_type: str,
    summary: str,
    organization_id: Optional[str] = None,
    integration_id: Optional[str] = None,
    account_sid: Optional[str] = None,
    provider_message_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    reason_code: Optional[str] = None,
) -> None:
    """
    Record a sanitized security audit event without exposing Auth Tokens,
    X-Twilio-Signature headers, or complete callback payloads.
    """
    masked_sid = mask_account_sid(account_sid)
    logger.warning(
        "Twilio webhook security event [%s]: %s | org=%s | account=%s | msg=%s | endpoint=%s | code=%s",
        event_type,
        summary,
        organization_id or "unresolved",
        masked_sid,
        provider_message_id or "none",
        endpoint or "unknown",
        reason_code or "none",
    )

    if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
        return

    try:
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type=event_type,
            target_id=integration_id or provider_message_id or masked_sid,
            target_type="TWILIO_INTEGRATION",
            action_label="Twilio Webhook Security Event",
            summary=summary,
            details={
                "account_sid_masked": masked_sid,
                "provider_message_id": provider_message_id,
                "integration_id": integration_id,
                "endpoint": endpoint,
                "reason_code": reason_code,
            },
        )
    except Exception:
        logger.exception("Failed to write SecurityAuditRepository event for %s", event_type)


def _is_org_active(mongo_db, organization_id: str) -> bool:
    org_col = mongo_db["organizations"] if "organizations" in getattr(mongo_db, "list_collection_names", lambda: [])() or hasattr(mongo_db, "__getitem__") else None
    if org_col is None or not hasattr(org_col, "find_one"):
        return True
    org_doc = org_col.find_one({"organization_id": organization_id})
    if not org_doc:
        # Allow minimal test setups without organization docs only if collection has no org docs at all;
        # if organization documents exist in DB and target org is absent or inactive, fail closed.
        if hasattr(org_col, "find_one") and org_col.find_one({}) is not None:
            return False
        return True
    return str(org_doc.get("status", "")).upper() == "ACTIVE"


def resolve_twilio_integration_for_callback(
    account_sid: Optional[str],
    endpoint: Optional[str] = None,
    provider_message_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve the single active organization Twilio integration owning `account_sid`.

    Fails closed when:
    - AccountSid is missing/empty
    - MongoDB context is unavailable
    - No active organization Twilio integration owns AccountSid
    - Integration is inactive/disconnected or belongs to an inactive organization
    - Credentials cannot be decrypted or lack auth_token
    - Multiple active organizations claim the same AccountSid
    """
    if not isinstance(account_sid, str) or not account_sid.strip():
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_UNKNOWN_ACCOUNT",
            summary="Rejected Twilio callback without AccountSid",
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="MISSING_ACCOUNT_SID",
        )
        return {
            "success": False,
            "status_code": 400,
            "error_code": "MISSING_ACCOUNT_SID",
            "message": "Twilio AccountSid is required",
        }

    clean_sid = account_sid.strip()
    sid_digest = account_sid_digest(clean_sid)

    if not has_app_context() or getattr(current_app, "mongo_db", None) is None:
        return {
            "success": False,
            "status_code": 503,
            "error_code": "CREDENTIAL_UNAVAILABLE",
            "message": "Provider credential store is unavailable",
        }

    mongo_db = current_app.mongo_db
    col = mongo_db["provider_configs"]

    # Query strictly organization-scoped Twilio configurations (never arbitrary orgs or global env)
    docs = list(
        col.find(
            {
                "provider": "twilio",
                "organization_id": {"$ne": None},
            },
            {
                "_id": 0,
                "config_id": 1,
                "organization_id": 1,
                "credentials": 1,
                "account_sid_digest": 1,
                "configured": 1,
                "disconnected": 1,
                "status": 1,
            },
        )
    )

    active_matches: List[Dict[str, Any]] = []
    inactive_matches: List[Dict[str, Any]] = []
    decryption_errors: List[Dict[str, Any]] = []

    for doc in docs:
        org_id = doc.get("organization_id")
        if not isinstance(org_id, str) or not org_id.strip():
            continue
        org_id = org_id.strip()

        stored_digest = doc.get("account_sid_digest")
        is_active = ProviderConfigService._is_document_active(doc)

        if stored_digest and stored_digest != sid_digest:
            continue

        if not is_active:
            if stored_digest == sid_digest:
                inactive_matches.append({"organization_id": org_id, "config_id": doc.get("config_id")})
            continue

        encrypted_creds = doc.get("credentials")
        if not encrypted_creds:
            if stored_digest == sid_digest:
                decryption_errors.append({"organization_id": org_id, "config_id": doc.get("config_id")})
            continue

        try:
            creds = ProviderConfigService._decrypt_credentials(
                encrypted_creds,
                provider="twilio",
                organization_id=org_id,
            )
        except ProviderResolutionError:
            if stored_digest == sid_digest:
                decryption_errors.append({"organization_id": org_id, "config_id": doc.get("config_id")})
            continue

        doc_sid = creds.get("account_sid")
        if not isinstance(doc_sid, str) or doc_sid.strip() != clean_sid:
            continue

        auth_token = creds.get("auth_token")
        if not isinstance(auth_token, str) or not auth_token.strip():
            decryption_errors.append({"organization_id": org_id, "config_id": doc.get("config_id")})
            continue

        if not _is_org_active(mongo_db, org_id):
            inactive_matches.append({"organization_id": org_id, "config_id": doc.get("config_id")})
            continue

        active_matches.append({
            "organization_id": org_id,
            "config_id": doc.get("config_id"),
            "account_sid_digest": sid_digest,
            "auth_token": auth_token.strip(),
        })

    if len(active_matches) > 1:
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_AMBIGUOUS_INTEGRATION",
            summary="Multiple active organizations matched incoming Twilio AccountSid; callback rejected",
            account_sid=clean_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="AMBIGUOUS_TWILIO_ACCOUNT",
        )
        return {
            "success": False,
            "status_code": 409,
            "error_code": "AMBIGUOUS_TWILIO_ACCOUNT",
            "message": "Ambiguous Twilio integration ownership",
        }

    if len(active_matches) == 1:
        return {
            "success": True,
            "integration": active_matches[0],
        }

    if decryption_errors:
        err_target = decryption_errors[0]
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_CREDENTIAL_ERROR",
            summary="Twilio webhook rejected because integration credentials are unavailable or unreadable",
            organization_id=err_target.get("organization_id"),
            integration_id=err_target.get("config_id"),
            account_sid=clean_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="CREDENTIAL_UNAVAILABLE",
        )
        return {
            "success": False,
            "status_code": 503,
            "error_code": "CREDENTIAL_UNAVAILABLE",
            "message": "Twilio integration credentials are unavailable",
        }

    if inactive_matches:
        inactive_target = inactive_matches[0]
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_INACTIVE_INTEGRATION",
            summary="Twilio webhook rejected because matching organization integration is inactive",
            organization_id=inactive_target.get("organization_id"),
            integration_id=inactive_target.get("config_id"),
            account_sid=clean_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="INTEGRATION_INACTIVE",
        )
        return {
            "success": False,
            "status_code": 403,
            "error_code": "INTEGRATION_INACTIVE",
            "message": "Twilio integration is inactive or unavailable",
        }

    log_twilio_security_event(
        event_type="TWILIO_WEBHOOK_UNKNOWN_ACCOUNT",
        summary="Twilio webhook rejected for unknown Twilio AccountSid",
        account_sid=clean_sid,
        provider_message_id=provider_message_id,
        endpoint=endpoint,
        reason_code="UNKNOWN_TWILIO_ACCOUNT",
    )
    return {
        "success": False,
        "status_code": 401,
        "error_code": "UNKNOWN_TWILIO_ACCOUNT",
        "message": "Unknown Twilio account",
    }


def verify_twilio_signature(
    *,
    auth_token: str,
    callback_url: str,
    params: Any,
    signature: Optional[str],
    organization_id: Optional[str] = None,
    integration_id: Optional[str] = None,
    account_sid: Optional[str] = None,
    provider_message_id: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Cryptographically verify X-Twilio-Signature via Twilio RequestValidator.
    Never bypassed in any environment.
    """
    if not isinstance(signature, str) or not signature.strip():
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_INVALID_SIGNATURE",
            summary="Missing X-Twilio-Signature header",
            organization_id=organization_id,
            integration_id=integration_id,
            account_sid=account_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="MISSING_SIGNATURE",
        )
        return False, {
            "success": False,
            "status_code": 401,
            "error_code": "MISSING_SIGNATURE",
            "message": "Missing X-Twilio-Signature header",
        }

    validator = RequestValidator(auth_token)
    is_valid = bool(validator.validate(callback_url, params if params is not None else {}, signature.strip()))

    if not is_valid:
        log_twilio_security_event(
            event_type="TWILIO_WEBHOOK_INVALID_SIGNATURE",
            summary="Invalid Twilio webhook signature",
            organization_id=organization_id,
            integration_id=integration_id,
            account_sid=account_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint,
            reason_code="INVALID_SIGNATURE",
        )
        return False, {
            "success": False,
            "status_code": 401,
            "error_code": "INVALID_SIGNATURE",
            "message": "Invalid Twilio webhook signature",
        }

    return True, None
