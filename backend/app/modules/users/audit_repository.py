"""
SenderX Security & Role Audit Repository
Records immutable audit logs with write-time identity snapshots and human-readable formatting.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import uuid
from flask import current_app


EVENT_LABELS = {
    "EMPLOYEE_CREATED": "Employee Created",
    "EMPLOYEE_UPDATED": "Employee Updated",
    "EMPLOYEE_DEACTIVATED": "Employee Deactivated",
    "EMPLOYEE_ACTIVATED": "Employee Activated",
    "EMPLOYEE_DELETED": "Employee Deleted",
    "ACTIVATION_OTP_REQUESTED": "Activation Code Requested",
    "ACTIVATION_OTP_RESENT": "Activation Code Resent",
    "ACCOUNT_ACTIVATED": "Account Activated",
    "PASSWORD_RESET_REQUESTED": "Password Reset Requested",
    "PASSWORD_RESET_COMPLETED": "Password Reset Completed",
    "OTP_LOCKED": "Verification Code Locked",
    "ROLES_ASSIGNED": "Roles Assigned",
    "ROLE_CREATED": "Role Created",
    "ROLE_UPDATED": "Role Updated",
    "ROLE_DELETED": "Role Deleted",
    "PROFILE_UPDATED": "Profile Updated",
    "ORG_ADMIN_PROFILE_UPDATED": "Admin Profile Updated",
    "ORGANIZATION_CHANGE_REQUEST_SUBMITTED": "Organization Change Request Submitted",
    "ORGANIZATION_CHANGE_REQUEST_APPROVED": "Organization Change Request Approved",
    "ORGANIZATION_CHANGE_REQUEST_REJECTED": "Organization Change Request Rejected",
    "ORGANIZATION_CHANGE_REQUEST_CANCELLED": "Organization Change Request Cancelled",
    "ORGANIZATION_DELETED": "Organization Deleted",
    "APPLICATION_REGISTERED": "Application Registered",
    "APPLICATION_ACTIVATED": "Application Activated",
    "APPLICATION_DEACTIVATED": "Application Deactivated",
    "API_CREDENTIAL_REGISTERED": "API Key Registered",
    "API_CREDENTIAL_UPDATED": "API Key Updated",
    "API_CREDENTIAL_REPLACED": "API Key Replaced",
    "API_CREDENTIAL_DELETED": "API Key Deleted",
    "WHATSAPP_INTEGRATION_CREATED": "WhatsApp Integration Connected",
    "WHATSAPP_INTEGRATION_CONNECTED": "WhatsApp Integration Connected",
    "WHATSAPP_INTEGRATION_VERIFIED": "WhatsApp Integration Verified",
    "WHATSAPP_INTEGRATION_VERIFICATION_FAILED": "WhatsApp Integration Verification Failed",
    "WHATSAPP_INTEGRATION_UPDATED": "WhatsApp Integration Updated",
    "WHATSAPP_CREDENTIALS_ROTATED": "WhatsApp Credentials Rotated",
    "WHATSAPP_INTEGRATION_DISCONNECTED": "WhatsApp Integration Disconnected",
    "WHATSAPP_INTEGRATION_RECONNECTED": "WhatsApp Integration Reconnected",
    "WHATSAPP_INTEGRATION_STATUS_CHECKED": "WhatsApp Credential Status Verified",
    "PLATFORM_SETTINGS_UPDATED": "Platform Settings Updated"
}

SENSITIVE_KEYS = {
    "password", "password_hash", "current_password", "new_password",
    "token", "refresh_token", "access_token", "encrypted_access_token", "secret", "api_key",
    "private_key", "secret_key", "meta_app_secret", "encrypted_app_secret", "otp",
    "verification_code", "reset_token", "webhook_verify_token", "encrypted_webhook_verify_token"
}


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively mask or remove sensitive authentication data."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(val, list):
        return [sanitize_sensitive_data(item) for item in val]
    return val


def generate_human_summary(
    event_type: str,
    action_label: str,
    actor_name: Optional[str],
    target_name: Optional[str],
    organization_name: Optional[str],
    details: Optional[Dict[str, Any]] = None
) -> str:
    """Construct a clean, human-readable sentence for the audit log entry."""
    details = details or {}
    t_name = target_name or "Target"
    a_name = actor_name or "Administrator"
    org_name = organization_name or "Organization"

    if event_type == "EMPLOYEE_DELETED":
        code_str = f" ({details.get('employee_code')})" if details.get("employee_code") else ""
        return f"Deleted employee {t_name}{code_str}"
    elif event_type == "EMPLOYEE_CREATED":
        code_str = f" ({details.get('employee_code')})" if details.get("employee_code") else ""
        return f"Created employee {t_name}{code_str}"
    elif event_type == "EMPLOYEE_UPDATED":
        return f"Updated employee {t_name}"
    elif event_type == "EMPLOYEE_DEACTIVATED":
        return f"Deactivated employee {t_name}"
    elif event_type == "EMPLOYEE_ACTIVATED":
        return f"Activated employee {t_name}"
    elif event_type == "ACTIVATION_OTP_REQUESTED":
        return f"Requested an activation code for {t_name}"
    elif event_type == "ACTIVATION_OTP_RESENT":
        return f"Resent an activation code for {t_name}"
    elif event_type == "ACCOUNT_ACTIVATED":
        return f"Activated account for {t_name}"
    elif event_type == "PASSWORD_RESET_REQUESTED":
        return f"Requested a password reset for {t_name}"
    elif event_type == "PASSWORD_RESET_COMPLETED":
        return f"Reset the password for {t_name}"
    elif event_type == "OTP_LOCKED":
        return f"Locked a verification code for {t_name} after failed attempts"
    elif event_type == "ROLES_ASSIGNED":
        return f"Assigned roles to {t_name}"
    elif event_type == "ROLE_CREATED":
        return f"Created role '{t_name}'"
    elif event_type == "ROLE_UPDATED":
        return f"Updated role '{t_name}'"
    elif event_type == "ROLE_DELETED":
        return f"Deleted role '{t_name}'"
    elif event_type in ("PROFILE_UPDATED", "ORG_ADMIN_PROFILE_UPDATED"):
        return f"Updated profile for {t_name or a_name}"
    elif event_type == "ORGANIZATION_CHANGE_REQUEST_SUBMITTED":
        return f"Submitted organization change request for {org_name}"
    elif event_type == "ORGANIZATION_CHANGE_REQUEST_APPROVED":
        return f"Approved organization change request for {org_name}"
    elif event_type == "ORGANIZATION_CHANGE_REQUEST_REJECTED":
        reason = f": {details.get('rejection_reason')}" if details.get("rejection_reason") else ""
        return f"Rejected organization change request for {org_name}{reason}"
    elif event_type == "ORGANIZATION_CHANGE_REQUEST_CANCELLED":
        return f"Cancelled organization change request for {org_name}"
    elif event_type == "ORGANIZATION_DELETED":
        return f"Deleted organization {org_name}"
    elif event_type == "APPLICATION_REGISTERED":
        return f"Registered application '{t_name}'"
    elif event_type == "APPLICATION_ACTIVATED":
        return f"Activated application '{t_name}'"
    elif event_type == "APPLICATION_DEACTIVATED":
        return f"Deactivated application '{t_name}'"
    else:
        return f"{action_label} for {t_name}"


class SecurityAuditRepository:
    """Persistence repository for security and role audit events."""

    COLLECTION = "security_audit_logs"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def log_event(
        cls,
        organization_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role_label: Optional[str] = None,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        organization_name: Optional[str] = None,
        action_label: Optional[str] = None,
        summary: Optional[str] = None,
        diff: Optional[Dict[str, Any]] = None,
        result: Optional[str] = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an immutable security audit entry with write-time identity snapshots."""
        db = current_app.mongo_db

        # 1. Resolve Actor Snapshot if missing
        if actor_id and (not actor_name or not actor_email or not actor_role_label):
            try:
                u_doc = db["users"].find_one({"user_id": actor_id})
                if u_doc:
                    actor_name = actor_name or u_doc.get("name") or u_doc.get("email")
                    actor_email = actor_email or u_doc.get("email")
                    if not actor_role_label:
                        r_name = "ORG_ADMIN" if u_doc.get("role_ids") and "org_admin" in str(u_doc.get("role_ids")).lower() else "Employee"
                        actor_role_label = "Organization Admin" if r_name == "ORG_ADMIN" else "Employee"
                else:
                    adm = db["admins"].find_one({"admin_id": actor_id})
                    if adm:
                        actor_name = actor_name or adm.get("name") or adm.get("email")
                        actor_email = actor_email or adm.get("email")
                        actor_role_label = actor_role_label or ("Platform Super Admin" if adm.get("role") == "SUPER_ADMIN" else "Platform Admin")
            except Exception:
                pass

        actor_name = actor_name or actor_email or "System / Automated"
        actor_email = actor_email or "system@senderx.io"
        actor_role_label = actor_role_label or "Administrator"

        # 2. Resolve Target Snapshot if missing
        if target_id and not target_name:
            try:
                if target_type == "USER" or not target_type:
                    u = db["users"].find_one({"user_id": target_id})
                    if u:
                        target_name = u.get("name") or u.get("email")
                        target_type = "USER"
                if target_type == "ROLE" or not target_name:
                    r = db["roles"].find_one({"role_id": target_id})
                    if r:
                        target_name = r.get("name")
                        target_type = "ROLE"
                if target_type == "ORGANIZATION" or not target_name:
                    o = db["organizations"].find_one({"organization_id": target_id})
                    if o:
                        target_name = o.get("name")
                        target_type = "ORGANIZATION"
                if target_type == "APPLICATION" or not target_name:
                    a = db["applications"].find_one({"application_id": target_id})
                    if a:
                        target_name = a.get("name")
                        target_type = "APPLICATION"
            except Exception:
                pass

        target_name = target_name or (f"ID: {target_id}" if target_id else "System")
        target_type = target_type or "SYSTEM"

        # 3. Resolve Organization Name Snapshot if missing
        if organization_id and not organization_name:
            try:
                org_doc = db["organizations"].find_one({"organization_id": organization_id})
                if org_doc:
                    organization_name = org_doc.get("name")
            except Exception:
                pass
        organization_name = organization_name or "Organization Workspace"

        # 4. Resolve Action Label & Human Summary
        clean_action_label = action_label or EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
        clean_summary = summary or generate_human_summary(
            event_type=event_type,
            action_label=clean_action_label,
            actor_name=actor_name,
            target_name=target_name,
            organization_name=organization_name,
            details=details
        )

        # 5. Sanitize sensitive data from details and diff
        clean_details = sanitize_sensitive_data(details or {})
        clean_diff = sanitize_sensitive_data(diff or {})

        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        entry = {
            "audit_id": audit_id,
            "organization_id": organization_id,
            "organization_name": organization_name,
            "event_type": event_type,
            "action_label": clean_action_label,
            "summary": clean_summary,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "actor_email": actor_email,
            "actor_role_label": actor_role_label,
            "target_id": target_id,
            "target_type": target_type,
            "target_name": target_name,
            "result": (result or "SUCCESS").upper(),
            "details": clean_details,
            "diff": clean_diff,
            "ip_address": ip_address,
            "timestamp": cls._now()
        }
        cls._collection().insert_one(entry)
        entry.pop("_id", None)
        return entry

    @classmethod
    def _format_entry(cls, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Format an audit log document for human readability, enriching legacy records."""
        entry = dict(doc)
        entry.pop("_id", None)

        event_type = entry.get("event_type", "UNKNOWN")
        action_label = entry.get("action_label") or EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
        entry["action_label"] = action_label

        actor_name = entry.get("actor_name")
        if not actor_name:
            actor_name = entry.get("actor_email") or (f"User {entry.get('actor_id')}" if entry.get("actor_id") else "System")
        entry["actor_name"] = actor_name
        entry["actor_email"] = entry.get("actor_email") or "system@senderx.io"
        entry["actor_role_label"] = entry.get("actor_role_label") or "Administrator"

        target_name = entry.get("target_name")
        if not target_name:
            details = entry.get("details", {})
            if isinstance(details, dict) and details.get("name"):
                target_name = details["name"]
            elif entry.get("target_id"):
                target_name = "Unknown (deleted)"
            else:
                target_name = "System"
        entry["target_name"] = target_name

        if not entry.get("summary"):
            entry["summary"] = generate_human_summary(
                event_type=event_type,
                action_label=action_label,
                actor_name=actor_name,
                target_name=target_name,
                organization_name=entry.get("organization_name"),
                details=entry.get("details")
            )

        entry["result"] = (entry.get("result") or "SUCCESS").upper()
        entry["details"] = sanitize_sensitive_data(entry.get("details") or {})
        entry["diff"] = sanitize_sensitive_data(entry.get("diff") or {})
        return entry

    @classmethod
    def find_by_organization(
        cls,
        organization_id: Optional[str] = None,
        target_id: Optional[str] = None,
        event_type: Optional[str] = None,
        search: Optional[str] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """Query security audit logs with comprehensive filters, search, and pagination."""
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        query: Dict[str, Any] = {}
        if organization_id:
            query["organization_id"] = organization_id
        if target_id:
            query["target_id"] = target_id
        if event_type:
            query["event_type"] = event_type

        # Action / Event category filter
        if action:
            action_clean = str(action).strip().upper()
            if action_clean in EVENT_LABELS:
                query["event_type"] = action_clean
            elif action_clean == "EMPLOYEE":
                query["event_type"] = {"$regex": "^EMPLOYEE_"}
            elif action_clean == "ROLE":
                query["event_type"] = {"$regex": "^ROLE"}
            elif action_clean == "ORGANIZATION":
                query["event_type"] = {"$regex": "^ORGANIZATION_"}
            elif action_clean == "APPLICATION":
                query["event_type"] = {"$regex": "^APPLICATION_"}
            else:
                query["event_type"] = {"$regex": f"^{re.escape(action_clean)}", "$options": "i"}

        # Actor filter
        if actor:
            actor_clean = str(actor).strip()
            query["$or"] = [
                {"actor_id": actor_clean},
                {"actor_email": {"$regex": re.escape(actor_clean), "$options": "i"}},
                {"actor_name": {"$regex": re.escape(actor_clean), "$options": "i"}}
            ]

        # Result filter (SUCCESS / FAILED)
        if result:
            query["result"] = str(result).strip().upper()

        # Date range filter
        if start_date or end_date:
            ts_query = {}
            if start_date:
                ts_query["$gte"] = start_date
            if end_date:
                ts_query["$lte"] = end_date
            query["timestamp"] = ts_query

        # Free-text Search across actor, target, action, summary
        if search:
            search_clean = str(search).strip()
            if search_clean:
                search_regex = {"$regex": re.escape(search_clean), "$options": "i"}
                search_clause = [
                    {"actor_name": search_regex},
                    {"actor_email": search_regex},
                    {"target_name": search_regex},
                    {"action_label": search_regex},
                    {"summary": search_regex},
                    {"event_type": search_regex}
                ]
                if "$or" in query:
                    query = {"$and": [query, {"$or": search_clause}]}
                else:
                    query["$or"] = search_clause

        total = cls._collection().count_documents(query)
        raw_items = list(
            cls._collection()
            .find(query)
            .sort("timestamp", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        formatted_items = [cls._format_entry(item) for item in raw_items]

        return {
            "items": formatted_items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
