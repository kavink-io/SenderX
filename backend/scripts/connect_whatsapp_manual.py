"""
Secure Operator Script: Connect WhatsApp Business Account via SenderX API
=========================================================================
Prompts interactively via getpass.getpass() (non-echoing) for:
  1. Organization authentication (existing JWT or email + password login)
  2. Meta WhatsApp Cloud API access token

Calls the existing authenticated POST /api/v1/whatsapp/integrations/connect
endpoint, verifies the new integration via GET /api/v1/whatsapp/integrations,
and confirms the existing prior integration remains untouched.

Security guarantees:
- Never prints or logs tokens, passwords, or Authorization headers.
- Never writes plaintext credentials to disk, .env, or exception messages.
- Clears secrets from local memory immediately after use.
- Never dispatches WhatsApp messages.
"""

import getpass
import json
import os
import sys
from typing import Optional
import requests


DEFAULT_API_BASE = os.environ.get("SENDERX_API_BASE", "http://127.0.0.1:5000/api/v1").rstrip("/")
TARGET_WABA_ID = "1163743516408340"
TARGET_PHONE_NUMBER_ID = "1592184223967764"
TARGET_NAME = "SenderX WhatsApp Business (+1 555-896-5150)"
EXPECTED_ORG_ID = "33a5292e-426c-4e89-94ee-87679b740188"
EXISTING_OLD_INTEGRATION_ID = "wai_3be7f699ddc24476acd7b6406c17a816"


def _obtain_org_jwt(api_base: str) -> str:
    """Obtain an authenticated organization JWT securely without hardcoding."""
    raw_jwt: Optional[str] = None
    password: Optional[str] = None
    try:
        raw_jwt = getpass.getpass(
            "Enter existing Organization JWT (leave blank to log in with email/password): "
        ).strip()
        if raw_jwt:
            return raw_jwt

        email = input("Enter Tidel Organization Admin email: ").strip().lower()
        if not email:
            raise RuntimeError("Organization email is required when JWT is not supplied.")

        password = getpass.getpass("Enter Organization Admin password (hidden): ")
        if not password:
            raise RuntimeError("Password cannot be empty.")

        resp = requests.post(
            f"{api_base}/auth/login",
            json={"email": email, "password": password},
            timeout=(5.0, 15.0),
        )
        try:
            body = resp.json()
        except ValueError:
            body = {}

        if resp.status_code != 200 or not body.get("success"):
            msg = body.get("message") or f"HTTP {resp.status_code}"
            raise RuntimeError(f"Authentication failed: {msg}")

        token = body.get("access_token") or (body.get("data") or {}).get("access_token")
        if not token:
            raise RuntimeError("Authentication response did not include an access_token.")
        return token
    finally:
        raw_jwt = None
        password = None


def _verify_org_access(api_base: str, org_jwt: str) -> dict:
    """Verify the JWT belongs to the active Tidel organization user account."""
    resp = requests.get(
        f"{api_base}/auth/me",
        headers={"Authorization": f"Bearer {org_jwt}"},
        timeout=(5.0, 15.0),
    )
    try:
        body = resp.json()
    except ValueError:
        body = {}

    if resp.status_code != 200 or not body.get("success"):
        msg = body.get("message") or f"HTTP {resp.status_code}"
        raise RuntimeError(f"Failed to verify organization context: {msg}")

    account = body.get("data") or {}
    org_id = account.get("organization_id")
    if account.get("account_type") != "ORGANIZATION_USER" or not org_id:
        raise RuntimeError("Authenticated account is not an ORGANIZATION_USER account.")
    if org_id != EXPECTED_ORG_ID:
        raise RuntimeError(f"Authenticated to unexpected organization '{org_id}'; expected Tidel ({EXPECTED_ORG_ID}).")

    return {
        "organization_id": org_id,
        "name": account.get("organization_name") or "Tidel",
        "email": account.get("email"),
    }


def main() -> int:
    api_base = DEFAULT_API_BASE
    org_jwt: Optional[str] = None
    meta_token: Optional[str] = None

    print(f"SenderX API Base : {api_base}")
    print(f"Target WABA ID   : {TARGET_WABA_ID}")
    print(f"Target Phone ID  : {TARGET_PHONE_NUMBER_ID}")
    print("Note: Input prompts are hidden and no credentials will be printed or saved to disk.\n")

    try:
        org_jwt = _obtain_org_jwt(api_base)
        org_info = _verify_org_access(api_base, org_jwt)
        print(f"Authenticated Organization: {org_info.get('name')} ({org_info.get('organization_id')})")

        meta_token = getpass.getpass(
            "Enter new Meta WhatsApp Access Token (hidden): "
        ).strip()
        if len(meta_token) < 10:
            print("ERROR: Meta access token must be at least 10 characters.", file=sys.stderr)
            return 1

        # Execute existing verified connect workflow
        connect_payload = {
            "waba_id": TARGET_WABA_ID,
            "phone_number_id": TARGET_PHONE_NUMBER_ID,
            "access_token": meta_token,
            "name": TARGET_NAME,
        }

        resp = requests.post(
            f"{api_base}/whatsapp/integrations/connect",
            headers={
                "Authorization": f"Bearer {org_jwt}",
                "Content-Type": "application/json",
            },
            json=connect_payload,
            timeout=(5.0, 20.0),
        )
        # Drop plaintext token reference as soon as request completes
        connect_payload["access_token"] = ""
        meta_token = None

        try:
            connect_body = resp.json()
        except ValueError:
            connect_body = {}

        if resp.status_code not in (200, 201) or not connect_body.get("success"):
            err_code = connect_body.get("error_code", "CONNECT_FAILED")
            meta_code = connect_body.get("meta_code")
            msg = connect_body.get("message") or f"HTTP {resp.status_code}"
            print(
                f"CONNECT FAILED (HTTP {resp.status_code}, {err_code}, meta_code={meta_code}): {msg}",
                file=sys.stderr,
            )
            return 1

        created = connect_body.get("data") or {}
        new_id = created.get("integration_id")

        # Read-only verification via authenticated API
        list_resp = requests.get(
            f"{api_base}/whatsapp/integrations",
            headers={"Authorization": f"Bearer {org_jwt}"},
            timeout=(5.0, 15.0),
        )
        list_body = list_resp.json() if list_resp.status_code == 200 else {}
        items = list_body.get("data") or []

        new_record = next((i for i in items if i.get("integration_id") == new_id), created)
        old_record = next((i for i in items if i.get("integration_id") == EXISTING_OLD_INTEGRATION_ID), None)

        print("\n=== Connection & Verification Summary (Secrets Excluded) ===")
        print(json.dumps({
            "new_integration": {
                "integration_id": new_record.get("integration_id"),
                "organization_id": new_record.get("organization_id"),
                "status": new_record.get("status"),
                "token_status": new_record.get("token_status"),
                "has_access_token": new_record.get("has_access_token"),
                "waba_id": new_record.get("waba_id"),
                "phone_number_id": new_record.get("phone_number_id"),
                "display_phone_number": new_record.get("display_phone_number"),
                "verified_name": new_record.get("verified_name"),
                "quality_rating": new_record.get("quality_rating"),
                "code_verification_status": new_record.get("code_verification_status"),
                "onboarding_method": new_record.get("onboarding_method"),
            },
            "existing_old_integration_untouched": {
                "present": old_record is not None,
                "integration_id": old_record.get("integration_id") if old_record else None,
                "phone_number_id": old_record.get("phone_number_id") if old_record else None,
                "waba_id": old_record.get("waba_id") if old_record else None,
                "status": old_record.get("status") if old_record else None,
            },
            "total_active_integrations": len(items),
        }, indent=2))

        if (
            new_record.get("status") == "CONNECTED"
            and new_record.get("waba_id") == TARGET_WABA_ID
            and new_record.get("phone_number_id") == TARGET_PHONE_NUMBER_ID
            and new_record.get("has_access_token") is True
            and old_record is not None
        ):
            print("\nSUCCESS: Correct WhatsApp Business Account connected and verified.")
            return 0

        print("\nWARNING: Post-connect verification checks did not all match expected values.", file=sys.stderr)
        return 1

    except requests.exceptions.RequestException as exc:
        print(f"Network error contacting SenderX API: {type(exc).__name__}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Operation aborted: {exc}", file=sys.stderr)
        return 1
    finally:
        org_jwt = None
        meta_token = None


if __name__ == "__main__":
    raise SystemExit(main())
