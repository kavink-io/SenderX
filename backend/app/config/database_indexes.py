"""
SenderX Database Indexes Configuration
Ensures proper unique, single-field, and compound indexes across all MongoDB collections.
"""

from flask import current_app
import pymongo


_ensured_dbs = set()


def ensure_database_indexes(app=None, force=False):
    db = (app.mongo_db if app else current_app.mongo_db)
    db_name = db.name
    if not force and db_name in _ensured_dbs:
        return

    # 1. Organizations
    db["organizations"].create_index([("organization_id", pymongo.ASCENDING)], unique=True)
    db["organizations"].create_index([("slug", pymongo.ASCENDING)], unique=True)
    db["organizations"].create_index([("status", pymongo.ASCENDING)])
    db["organizations"].create_index([("created_at", pymongo.DESCENDING)])

    # Organization Change Requests
    db["organization_change_requests"].create_index([("request_id", pymongo.ASCENDING)], unique=True)
    db["organization_change_requests"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["organization_change_requests"].create_index([("created_at", pymongo.DESCENDING)])

    # 2. Admins
    db["admins"].create_index([("admin_id", pymongo.ASCENDING)], unique=True)
    db["admins"].create_index([("email", pymongo.ASCENDING)], unique=True)

    # 3. Users
    db["users"].create_index([("user_id", pymongo.ASCENDING)], unique=True)
    try:
        db["users"].create_index(
            [("email", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"deleted_at": None}
        )
    except pymongo.errors.OperationFailure:
        try:
            db["users"].drop_index("email_1")
        except Exception:
            pass
        db["users"].create_index(
            [("email", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"deleted_at": None}
        )

    db["users"].create_index([("organization_id", pymongo.ASCENDING)])

    try:
        db["users"].create_index(
            [("organization_id", pymongo.ASCENDING), ("employee_code", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={
                "employee_code": {"$type": "string"},
                "deleted_at": None
            }
        )
    except pymongo.errors.OperationFailure:
        try:
            db["users"].drop_index("organization_id_1_employee_code_1")
        except Exception:
            pass
        db["users"].create_index(
            [("organization_id", pymongo.ASCENDING), ("employee_code", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={
                "employee_code": {"$type": "string"},
                "deleted_at": None
            }
        )

    try:
        db["users"].create_index(
            [("organization_id", pymongo.ASCENDING), ("employee_code_lower", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={
                "employee_code_lower": {"$type": "string"},
                "deleted_at": None
            }
        )
    except pymongo.errors.OperationFailure:
        try:
            db["users"].drop_index("organization_id_1_employee_code_lower_1")
        except Exception:
            pass
        db["users"].create_index(
            [("organization_id", pymongo.ASCENDING), ("employee_code_lower", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={
                "employee_code_lower": {"$type": "string"},
                "deleted_at": None
            }
        )
    db["users"].create_index([("organization_id", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING)])
    db["users"].create_index([("organization_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])

    # 4. Roles
    db["roles"].create_index([("role_id", pymongo.ASCENDING)], unique=True)
    db["roles"].create_index([("organization_id", pymongo.ASCENDING), ("name", pymongo.ASCENDING)], unique=True)

    # 5. Messages
    db["messages"].create_index([("message_id", pymongo.ASCENDING)], unique=True)
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("provider", pymongo.ASCENDING)])
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("channel", pymongo.ASCENDING)])
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("recipient", pymongo.ASCENDING)])
    db["messages"].create_index([("provider_message_id", pymongo.ASCENDING)])
    db["messages"].create_index([("organization_id", pymongo.ASCENDING), ("provider_message_id", pymongo.ASCENDING)])

    # 6. Dead Letters
    db["dead_letters"].create_index([("message_id", pymongo.ASCENDING)], unique=True)
    db["dead_letters"].create_index([("message_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)], unique=True)
    db["dead_letters"].create_index([
        ("dead_letter_status", pymongo.ASCENDING),
        ("manual_retry_dispatch_state", pymongo.ASCENDING),
        ("manual_retry_dispatch_started_at", pymongo.ASCENDING)
    ])
    db["dead_letters"].create_index([("organization_id", pymongo.ASCENDING), ("dead_letter_status", pymongo.ASCENDING)])
    db["dead_letters"].create_index([("organization_id", pymongo.ASCENDING), ("manual_retry_dispatch_state", pymongo.ASCENDING)])
    db["dead_letters"].create_index([("organization_id", pymongo.ASCENDING), ("created_in_dlq_at", pymongo.DESCENDING)])

    # 7. Provider Configs
    db["provider_configs"].create_index(
        [("provider", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)],
        unique=True
    )

    # 8. Templates
    db["templates"].create_index([("template_id", pymongo.ASCENDING)], unique=True)
    try:
        db["templates"].create_index(
            [("organization_id", pymongo.ASCENDING), ("name_lower", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"status": {"$in": ["ACTIVE", "DRAFT"]}, "name_lower": {"$type": "string"}}
        )
    except pymongo.errors.OperationFailure as e:
        if "IndexKeySpecsConflict" in str(e) or getattr(e, "code", None) == 86:
            try:
                db["templates"].drop_index("organization_id_1_name_lower_1")
            except Exception:
                pass
            db["templates"].create_index(
                [("organization_id", pymongo.ASCENDING), ("name_lower", pymongo.ASCENDING)],
                unique=True,
                partialFilterExpression={"status": {"$in": ["ACTIVE", "DRAFT"]}, "name_lower": {"$type": "string"}}
            )
        else:
            raise
    db["templates"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["templates"].create_index([("organization_id", pymongo.ASCENDING), ("category", pymongo.ASCENDING)])
    db["templates"].create_index([("organization_id", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)])

    # 9. Template Versions
    db["template_versions"].create_index(
        [("template_id", pymongo.ASCENDING), ("version", pymongo.ASCENDING)],
        unique=True
    )
    db["template_versions"].create_index([("organization_id", pymongo.ASCENDING), ("template_id", pymongo.ASCENDING)])

    # 10. Media & Attachments
    db["media"].create_index([("media_id", pymongo.ASCENDING)], unique=True)
    db["media"].create_index([("organization_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
    db["media"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["media"].create_index([("organization_id", pymongo.ASCENDING), ("checksum_sha256", pymongo.ASCENDING)])
    db["media"].create_index([("organization_id", pymongo.ASCENDING), ("mime_type", pymongo.ASCENDING)])
    db["media"].create_index([("expires_at", pymongo.ASCENDING)])

    # 11. Ingested Payloads & Routing
    db["ingested_payloads"].create_index([("payload_id", pymongo.ASCENDING)], unique=True)
    db["ingested_payloads"].create_index([("organization_id", pymongo.ASCENDING), ("received_at", pymongo.DESCENDING)])
    db["ingested_payloads"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["ingested_payloads"].create_index([("organization_id", pymongo.ASCENDING), ("channel", pymongo.ASCENDING)])
    db["ingested_payloads"].create_index([("organization_id", pymongo.ASCENDING), ("application_id", pymongo.ASCENDING)])

    # 12. Payload Audit Logs
    db["payload_audit_logs"].create_index([("audit_id", pymongo.ASCENDING)], unique=True)
    db["payload_audit_logs"].create_index([("organization_id", pymongo.ASCENDING), ("payload_id", pymongo.ASCENDING)])
    db["payload_audit_logs"].create_index([("organization_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
    db["payload_audit_logs"].create_index([("payload_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])
    db["payload_audit_logs"].create_index([
        ("organization_id", pymongo.ASCENDING),
        ("payload_id", pymongo.ASCENDING),
        ("timestamp", pymongo.ASCENDING)
    ])

    # 13. API Credentials
    db["api_credentials"].create_index([("credential_id", pymongo.ASCENDING)], unique=True)
    db["api_credentials"].create_index([("key_hash", pymongo.ASCENDING)], unique=True)
    db["api_credentials"].create_index([("organization_id", pymongo.ASCENDING), ("application_id", pymongo.ASCENDING)])
    db["api_credentials"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])

    # 14. Connected Applications
    db["connected_applications"].create_index([("application_id", pymongo.ASCENDING)], unique=True)
    db["connected_applications"].create_index(
        [("organization_id", pymongo.ASCENDING), ("name", pymongo.ASCENDING)],
        unique=True
    )
    db["connected_applications"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["connected_applications"].create_index([("organization_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])

    # 15. Security & Role Audit Logs
    db["security_audit_logs"].create_index([("audit_id", pymongo.ASCENDING)], unique=True)
    db["security_audit_logs"].create_index([("organization_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
    db["security_audit_logs"].create_index([("target_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)])
    db["security_audit_logs"].create_index([("organization_id", pymongo.ASCENDING), ("event_type", pymongo.ASCENDING)])

    # 16. Authentication OTPs and short-lived password tokens
    db["auth_otps"].create_index([("otp_id", pymongo.ASCENDING)], unique=True)
    db["auth_otps"].create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0)
    db["auth_otps"].create_index([
        ("email", pymongo.ASCENDING),
        ("purpose", pymongo.ASCENDING),
        ("created_at", pymongo.DESCENDING)
    ])
    db["auth_otps"].create_index([("reset_token_hash", pymongo.ASCENDING)], sparse=True)
    db["auth_otps"].create_index([
        ("account_id", pymongo.ASCENDING),
        ("purpose", pymongo.ASCENDING)
    ])

    # 17. WhatsApp Integrations (Multi-Tenant Cloud API)
    db["whatsapp_integrations"].create_index([("integration_id", pymongo.ASCENDING)], unique=True)
    try:
        db["whatsapp_integrations"].create_index(
            [("phone_number_id", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"deleted_at": None}
        )
    except pymongo.errors.OperationFailure:
        try:
            db["whatsapp_integrations"].drop_index("phone_number_id_1")
        except Exception:
            pass
        db["whatsapp_integrations"].create_index(
            [("phone_number_id", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"deleted_at": None}
        )
    db["whatsapp_integrations"].create_index([("organization_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
    db["whatsapp_integrations"].create_index([("organization_id", pymongo.ASCENDING), ("deleted_at", pymongo.ASCENDING)])
    db["whatsapp_integrations"].create_index([("waba_id", pymongo.ASCENDING)])
    db["whatsapp_integrations"].create_index([("organization_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])

    # Flow completion values are encrypted in a dedicated collection. MongoDB
    # TTL removes only these new encrypted records; historical inbound records
    # without this schema are left untouched for an explicit migration decision.
    db["whatsapp_flow_responses"].create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0)
    db["whatsapp_flow_responses"].create_index([
        ("organization_id", pymongo.ASCENDING),
        ("integration_id", pymongo.ASCENDING),
        ("provider_message_id", pymongo.ASCENDING),
    ], unique=True)
    db["whatsapp_flow_exchange_requests"].create_index([
        ("organization_id", pymongo.ASCENDING),
        ("integration_id", pymongo.ASCENDING),
        ("flow_id", pymongo.ASCENDING),
    ])

    # 18. Platform Settings (Centralized Meta Platform Configuration)
    db["platform_settings"].create_index([("setting_key", pymongo.ASCENDING)], unique=True)

    # 19. User-Specific Appearance & Layout Preferences
    db["user_preferences"].create_index(
        [("user_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)],
        unique=True,
    )
    db["user_preferences"].create_index([("organization_id", pymongo.ASCENDING)])

    _ensured_dbs.add(db_name)



