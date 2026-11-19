import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from flask import current_app
from pymongo import ReturnDocument

from app.adapters.adapter_registry import AdapterRegistry
from app.modules.auth.repository import AuthRepository
from app.modules.api_credentials.rate_limiter import (
    DistributedRateLimiter,
    RateLimiterError,
)
from app.modules.organizations.repository import OrganizationRepository
from app.modules.provider_config.service import ProviderConfigService
from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.users.repository import UserRepository


class OTPServiceError(Exception):
    def __init__(self, message, status_code=400, retry_after=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


class OTPService:
    ACTIVATION = "ACTIVATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    OTP_TTL = timedelta(minutes=10)
    RESET_TOKEN_TTL = timedelta(minutes=5)
    EMAIL_LIMIT = 5
    EMAIL_WINDOW_SECONDS = 60 * 60
    IP_LIMIT = 20
    IP_WINDOW_SECONDS = 60 * 60
    RESEND_COOLDOWN_SECONDS = 60
    MAX_ATTEMPTS = 5

    @classmethod
    def _collection(cls):
        return current_app.mongo_db["auth_otps"]

    @classmethod
    def _secret(cls):
        environment = str(current_app.config.get("APP_ENV", "development")).strip().lower()
        secret = current_app.config.get("OTP_HMAC_SECRET")
        if environment == "production":
            if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
                raise OTPServiceError(
                    "OTP_HMAC_SECRET must be set to at least 32 characters in production",
                    status_code=503
                )
        else:
            secret = (
                secret
                or current_app.config.get("JWT_SECRET_KEY")
                or current_app.config.get("SECRET_KEY")
            )
        if not isinstance(secret, str) or not secret:
            raise OTPServiceError(
                "Authentication code service is not configured",
                status_code=503
            )
        return secret.encode("utf-8")

    @classmethod
    def _digest(cls, purpose, email, value):
        payload = f"{purpose}:{email}:{value}".encode("utf-8")
        return hmac.new(cls._secret(), payload, hashlib.sha256).hexdigest()

    @classmethod
    def _queue_cipher(cls):
        key = hashlib.sha256(cls._secret() + b":senderx-auth-otp-email").digest()
        return Fernet(base64.urlsafe_b64encode(key))

    @classmethod
    def encrypt_email_payload(cls, email, purpose, code):
        payload = json.dumps({
            "email": email,
            "purpose": purpose,
            "code": code
        }).encode("utf-8")
        return cls._queue_cipher().encrypt(payload).decode("ascii")

    @classmethod
    def decrypt_email_payload(cls, encrypted_payload):
        payload = cls._queue_cipher().decrypt(encrypted_payload.encode("ascii"))
        decoded = json.loads(payload.decode("utf-8"))
        if (
            not isinstance(decoded, dict)
            or not isinstance(decoded.get("email"), str)
            or decoded.get("purpose") not in (cls.ACTIVATION, cls.PASSWORD_RESET)
            or not isinstance(decoded.get("code"), str)
        ):
            raise ValueError("Invalid authentication email payload")
        return decoded

    @classmethod
    def _environment_email_providers(cls):
        def setting(name):
            return current_app.config.get(name) or os.getenv(name)

        providers = set()
        if setting("SENDGRID_API_KEY") and setting("SENDGRID_FROM_EMAIL"):
            providers.add("sendgrid")

        if (
            setting("AWS_ACCESS_KEY_ID")
            and setting("AWS_SECRET_ACCESS_KEY")
            and (setting("AWS_SES_FROM_EMAIL") or setting("SENDGRID_FROM_EMAIL"))
        ):
            providers.add("ses")

        if (
            setting("SMTP_HOST")
            and (setting("SMTP_FROM_EMAIL") or setting("SENDGRID_FROM_EMAIL"))
        ):
            providers.add("smtp")

        return providers

    @classmethod
    def configured_email_provider(cls):
        statuses = ProviderConfigService.get_all_configuration_statuses()
        supported = {"sendgrid", "ses", "amazon_ses", "smtp"}
        configured = {
            status.get("provider")
            for status in statuses
            if status.get("configured")
            and status.get("organization_id") is None
            and status.get("provider") in supported
        }
        configured.update(cls._environment_email_providers())

        preferred = current_app.config.get("AUTH_OTP_EMAIL_PROVIDER")
        if preferred:
            preferred = str(preferred).strip().lower()
            if preferred == "mock":
                environment = str(current_app.config.get("APP_ENV", "development")).lower()
                if environment != "production" and (
                    current_app.config.get("TESTING")
                    or environment in ("development", "test")
                ):
                    return "mock"
                raise OTPServiceError(
                    "Mock authentication email is allowed only in development or test",
                    status_code=503
                )
            equivalent_configured = (
                preferred == "amazon_ses" and "ses" in configured
            ) or (
                preferred == "ses" and "amazon_ses" in configured
            )
            if preferred not in supported or (
                preferred not in configured and not equivalent_configured
            ):
                raise OTPServiceError(
                    "The selected authentication email provider is not configured",
                    status_code=503
                )
            return preferred

        if len(configured) == 1:
            return next(iter(configured))
        if len(configured) > 1:
            raise OTPServiceError(
                "Multiple platform email providers are configured; set AUTH_OTP_EMAIL_PROVIDER",
                status_code=503
            )

        environment = str(current_app.config.get("APP_ENV", "development")).lower()
        if environment != "production" and (
            current_app.config.get("TESTING")
            or environment in ("development", "test")
        ):
            return "mock"

        raise OTPServiceError(
            "No platform email provider is configured for authentication messages",
            status_code=503
        )

    @classmethod
    def _rate_limit(cls, email, client_ip):
        secret = cls._secret()
        email_key = hmac.new(secret, f"email:{email}".encode("utf-8"), hashlib.sha256).hexdigest()
        ip_key = hmac.new(secret, f"ip:{client_ip or 'unknown'}".encode("utf-8"), hashlib.sha256).hexdigest()

        try:
            cooldown_allowed, cooldown_retry = DistributedRateLimiter.check_rate_limit(
                "auth_otp_cooldown",
                email_key,
                limit=1,
                window_seconds=cls.RESEND_COOLDOWN_SECONDS
            )
            email_allowed, email_retry = DistributedRateLimiter.check_rate_limit(
                "auth_otp_email",
                email_key,
                limit=cls.EMAIL_LIMIT,
                window_seconds=cls.EMAIL_WINDOW_SECONDS
            )
            ip_allowed, ip_retry = DistributedRateLimiter.check_rate_limit(
                "auth_otp_ip",
                ip_key,
                limit=cls.IP_LIMIT,
                window_seconds=cls.IP_WINDOW_SECONDS
            )
        except RateLimiterError as error:
            raise OTPServiceError(
                "Authentication code service is temporarily unavailable",
                status_code=503
            ) from error

        if not cooldown_allowed:
            raise OTPServiceError(
                "Please wait before requesting another code",
                status_code=429,
                retry_after=cooldown_retry
            )
        if not email_allowed:
            raise OTPServiceError(
                "Too many code requests for this email. Try again later",
                status_code=429,
                retry_after=email_retry
            )
        if not ip_allowed:
            raise OTPServiceError(
                "Too many code requests from this network. Try again later",
                status_code=429,
                retry_after=ip_retry
            )

    @classmethod
    def _find_account(cls, email, purpose):
        if purpose == cls.ACTIVATION:
            user = UserRepository.find_by_email(email)
            return cls._user_account(user) if user else None

        admin = AuthRepository.find_by_email(email)
        if admin:
            return cls._admin_account(admin)

        user = UserRepository.find_by_email(email)
        return cls._user_account(user) if user else None

    @staticmethod
    def _user_account(user):
        return {
            "account_type": "USER",
            "account_id": user.get("user_id"),
            "organization_id": user.get("organization_id"),
            "email": user.get("email"),
            "name": user.get("name") or user.get("email"),
            "document": user
        }

    @staticmethod
    def _admin_account(admin):
        return {
            "account_type": "ADMIN",
            "account_id": admin.get("admin_id"),
            "organization_id": None,
            "email": admin.get("email"),
            "name": admin.get("name") or admin.get("email"),
            "document": admin
        }

    @classmethod
    def _is_deleted(cls, account):
        if account["account_type"] != "USER":
            return False
        user = account["document"]
        return (
            user.get("status") == "DELETED"
            or user.get("is_deleted") is True
            or user.get("deleted_at") is not None
        )

    @classmethod
    def _is_eligible(cls, account, purpose):
        if not account or cls._is_deleted(account):
            return False

        document = account["document"]
        if purpose == cls.ACTIVATION:
            if account["account_type"] != "USER":
                return False
            if document.get("status") != "PENDING_ACTIVATION" or document.get("is_active", True):
                return False
        elif not document.get("is_active", False):
            return False
        elif account["account_type"] == "USER" and document.get("status") in (
            "DELETED",
            "PENDING_ACTIVATION",
            "INACTIVE"
        ):
            return False

        if account["account_type"] == "USER":
            organization = OrganizationRepository.find_by_id(account["organization_id"])
            if not organization or organization.get("status") != "ACTIVE":
                return False

        return True

    @classmethod
    def _actor_role_label(cls, account):
        if account["account_type"] == "ADMIN":
            return "Platform Super Admin" if account["document"].get("role") == "SUPER_ADMIN" else "Platform Admin"

        role_ids = account["document"].get("role_ids", [])
        if role_ids:
            admin_role = current_app.mongo_db["roles"].find_one({
                "organization_id": account["organization_id"],
                "role_id": {"$in": role_ids},
                "name": "ORG_ADMIN"
            })
            if admin_role:
                return "Organization Admin"
        return "Employee"

    @classmethod
    def _write_audit(
        cls,
        event_type,
        account,
        ip_address,
        actor_id=None,
        actor_name=None,
        actor_email=None,
        actor_role_label=None,
        purpose=None
    ):
        is_self_service = actor_id is None
        SecurityAuditRepository.log_event(
            organization_id=account["organization_id"],
            event_type=event_type,
            actor_id=actor_id,
            actor_name=actor_name or (
                "Unverified account holder" if is_self_service else account["name"]
            ),
            actor_email=actor_email or account["email"],
            actor_role_label=actor_role_label or (
                "Unauthenticated account holder" if is_self_service
                else cls._actor_role_label(account)
            ),
            target_id=account["account_id"],
            target_type="USER" if account["account_type"] == "USER" else "ADMIN",
            target_name=account["name"],
            ip_address=ip_address,
            details={"purpose": purpose} if purpose else {}
        )

    @classmethod
    def request_code(
        cls,
        email,
        purpose,
        client_ip=None,
        target_user_id=None,
        organization_id=None,
        actor=None
    ):
        purpose = str(purpose or "").strip().upper()
        if purpose not in (cls.ACTIVATION, cls.PASSWORD_RESET):
            raise OTPServiceError("Invalid code purpose")

        email = email.strip().lower() if isinstance(email, str) else ""
        if len(email) > 254:
            email = ""

        provider = cls.configured_email_provider()
        cls._rate_limit(email, client_ip)

        account = None
        if target_user_id:
            user = UserRepository.find_by_id(
                target_user_id,
                organization_id=organization_id,
                include_deleted=True
            )
            account = cls._user_account(user) if user else None
            if not account or account["email"] != email:
                raise OTPServiceError("Pending employee was not found", status_code=404)
        elif email and purpose == cls.ACTIVATION:
            account = cls._find_account(email, purpose)
        elif email:
            account = cls._find_account(email, purpose)

        if not cls._is_eligible(account, purpose):
            if target_user_id:
                raise OTPServiceError(
                    "Only employees pending activation can receive an activation code",
                    status_code=409
                )
            return {
                "success": True,
                "message": cls._generic_message(purpose)
            }

        now = datetime.now(timezone.utc)
        code = f"{secrets.randbelow(1_000_000):06d}"
        record = {
            "otp_id": secrets.token_hex(16),
            "account_type": account["account_type"],
            "account_id": account["account_id"],
            "organization_id": account["organization_id"],
            "email": email,
            "purpose": purpose,
            "otp_hash": cls._digest(purpose, email, code),
            "status": "ACTIVE",
            "attempts": 0,
            "created_at": now,
            "expires_at": now + cls.OTP_TTL
        }

        cls._collection().update_many(
            {
                "email": email,
                "purpose": purpose,
                "status": {"$in": ["ACTIVE", "VERIFIED", "LOCKED"]}
            },
            {"$set": {"status": "INVALIDATED"}}
        )
        cls._collection().insert_one(record)

        try:
            from app.queue.tasks import send_auth_otp_email

            encrypted_payload = cls.encrypt_email_payload(email, purpose, code)
            send_auth_otp_email.apply_async(args=[encrypted_payload, provider])
        except Exception as error:
            cls._collection().update_one(
                {"otp_id": record["otp_id"], "status": "ACTIVE"},
                {"$set": {"status": "INVALIDATED"}}
            )
            current_app.logger.error(
                "Could not queue authentication email for purpose %s (%s)",
                purpose,
                type(error).__name__
            )
            if target_user_id:
                raise OTPServiceError(
                    "Could not send the activation code. Please try again later",
                    status_code=503
                ) from None
            return {
                "success": True,
                "message": cls._generic_message(purpose)
            }

        if purpose == cls.ACTIVATION:
            event_type = "ACTIVATION_OTP_RESENT" if actor else "ACTIVATION_OTP_REQUESTED"
        else:
            event_type = "PASSWORD_RESET_REQUESTED"

        if actor:
            actor_document = actor.get("document", {})
            cls._write_audit(
                event_type,
                account,
                client_ip,
                actor_id=actor.get("actor_id"),
                actor_name=actor_document.get("name") or actor_document.get("email"),
                actor_email=actor_document.get("email"),
                actor_role_label=actor.get("actor_role_label"),
                purpose=purpose
            )
        else:
            cls._write_audit(event_type, account, client_ip, purpose=purpose)

        return {
            "success": True,
            "message": cls._generic_message(purpose)
        }

    @classmethod
    def _generic_message(cls, purpose):
        if purpose == cls.PASSWORD_RESET:
            return "If an active account matches that email, a password reset code will be sent."
        return "If a pending account matches that email, an activation code will be sent."

    @classmethod
    def verify_code(cls, email, purpose, code, client_ip=None):
        purpose = str(purpose or "").strip().upper()
        email = email.strip().lower() if isinstance(email, str) else ""
        if purpose not in (cls.ACTIVATION, cls.PASSWORD_RESET) or not email:
            raise OTPServiceError("That code is invalid or expired. Request a new code.")

        record = cls._collection().find_one(
            {
                "email": email,
                "purpose": purpose,
                "status": {"$in": ["ACTIVE", "LOCKED", "VERIFIED"]}
            },
            sort=[("created_at", -1)]
        )
        if not record:
            raise OTPServiceError("That code is invalid or expired. Request a new code.")
        if record.get("status") == "LOCKED":
            raise OTPServiceError(
                "Too many incorrect attempts. Request a new code",
                status_code=429
            )
        if record.get("status") == "VERIFIED":
            raise OTPServiceError(
                "That code has already been used. Request a new code"
            )

        expiry = record.get("expires_at")
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if not expiry or expiry <= now:
            raise OTPServiceError(
                "That code has expired. Request a new one",
                status_code=410
            )

        account = cls._account_for_record(record)
        if not cls._is_eligible(account, purpose):
            cls._collection().update_one(
                {"_id": record["_id"], "status": "ACTIVE"},
                {"$set": {"status": "INVALIDATED"}}
            )
            raise OTPServiceError("That code is no longer valid. Request a new one")

        code_value = code if isinstance(code, str) else ""
        candidate_hash = cls._digest(purpose, email, code_value)
        stored_hash = record.get("otp_hash", "")
        if (
            len(code_value) != 6
            or not code_value.isdigit()
            or not isinstance(stored_hash, str)
            or not hmac.compare_digest(stored_hash, candidate_hash)
        ):
            return cls._record_failed_attempt(record, account, client_ip)

        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = cls._digest(purpose, "", reset_token)
        reset_expires = now + cls.RESET_TOKEN_TTL
        verified = cls._collection().find_one_and_update(
            {
                "_id": record["_id"],
                "status": "ACTIVE",
                "otp_hash": stored_hash,
                "expires_at": {"$gt": now},
                "attempts": {"$lt": cls.MAX_ATTEMPTS}
            },
            {
                "$set": {
                    "status": "VERIFIED",
                    "reset_token_hash": reset_token_hash,
                    "expires_at": reset_expires,
                    "verified_at": now
                },
                "$unset": {"otp_hash": ""}
            },
            return_document=ReturnDocument.AFTER
        )
        if not verified:
            raise OTPServiceError(
                "That code has expired or was already used. Request a new code",
                status_code=410
            )

        return {
            "success": True,
            "message": "Code verified. Set a new password to continue.",
            "data": {
                "reset_token": reset_token,
                "purpose": purpose,
                "expires_in": int(cls.RESET_TOKEN_TTL.total_seconds())
            }
        }

    @classmethod
    def _account_for_record(cls, record):
        if record.get("account_type") == "ADMIN":
            admin = AuthRepository.find_by_id(record.get("account_id"))
            return cls._admin_account(admin) if admin else None
        user = UserRepository.find_by_id(
            record.get("account_id"),
            include_deleted=True
        )
        return cls._user_account(user) if user else None

    @classmethod
    def _record_failed_attempt(cls, record, account, client_ip):
        updated = cls._collection().find_one_and_update(
            {
                "_id": record["_id"],
                "status": "ACTIVE",
                "attempts": {"$lt": cls.MAX_ATTEMPTS}
            },
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER
        )
        if not updated:
            current = cls._collection().find_one({"_id": record["_id"]})
            if current and current.get("status") == "LOCKED":
                raise OTPServiceError(
                    "Too many incorrect attempts. Request a new code",
                    status_code=429
                )
            raise OTPServiceError(
                "That code has expired or was already used. Request a new code",
                status_code=410
            )

        if updated["attempts"] >= cls.MAX_ATTEMPTS:
            locked = cls._collection().update_one(
                {"_id": record["_id"], "status": "ACTIVE"},
                {"$set": {"status": "LOCKED", "locked_at": datetime.now(timezone.utc)}}
            )
            if locked.modified_count:
                cls._write_audit(
                    "OTP_LOCKED",
                    account,
                    client_ip,
                    purpose=record.get("purpose")
                )
            raise OTPServiceError(
                "Too many incorrect attempts. Request a new code",
                status_code=429
            )

        raise OTPServiceError("That code is incorrect. Check it and try again")

    @classmethod
    def _password_error(cls, password):
        if not isinstance(password, str) or len(password) < 8:
            return "Password must be at least 8 characters long"
        if len(password.encode("utf-8")) > 72:
            return "Password must be no more than 72 bytes"
        if not any(char.isupper() for char in password):
            return "Password must include an uppercase letter"
        if not any(char.islower() for char in password):
            return "Password must include a lowercase letter"
        if not any(char.isdigit() for char in password):
            return "Password must include a number"
        if not any(not char.isalnum() for char in password):
            return "Password must include a special character"
        return None

    @classmethod
    def set_password(cls, purpose, reset_token, password):
        purpose = str(purpose or "").strip().upper()
        if purpose not in (cls.ACTIVATION, cls.PASSWORD_RESET):
            raise OTPServiceError("Invalid password update request")

        password_error = cls._password_error(password)
        if password_error:
            raise OTPServiceError(password_error)
        if not isinstance(reset_token, str) or not reset_token:
            raise OTPServiceError(
                "This password link is invalid or expired. Request a new code",
                status_code=410
            )

        now = datetime.now(timezone.utc)
        token_hash = cls._digest(purpose, "", reset_token)
        candidate = cls._collection().find_one({
            "purpose": purpose,
            "status": "VERIFIED",
            "expires_at": {"$gt": now},
            "reset_token_hash": token_hash
        })
        if (
            not candidate
            or not hmac.compare_digest(
                candidate.get("reset_token_hash", ""),
                token_hash
            )
        ):
            raise OTPServiceError(
                "This password link is invalid, expired or already used",
                status_code=410
            )

        matched_record = candidate
        account = cls._account_for_record(matched_record)
        if not cls._is_eligible(account, purpose):
            cls._collection().delete_many({"account_id": matched_record.get("account_id")})
            raise OTPServiceError("This account is no longer eligible for password changes", status_code=403)

        consumed = cls._collection().find_one_and_delete({
            "_id": matched_record["_id"],
            "status": "VERIFIED",
            "reset_token_hash": matched_record["reset_token_hash"],
            "expires_at": {"$gt": now}
        })
        if not consumed:
            raise OTPServiceError(
                "This password link is invalid, expired or already used",
                status_code=410
            )

        import bcrypt

        rounds = int(current_app.config.get("BCRYPT_ROUNDS", 12))
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=rounds)
        ).decode("utf-8")

        collection = current_app.mongo_db[
            "admins" if account["account_type"] == "ADMIN" else "users"
        ]
        identity_key = "admin_id" if account["account_type"] == "ADMIN" else "user_id"
        query = {identity_key: account["account_id"]}
        if account["account_type"] == "USER":
            query["organization_id"] = account["organization_id"]
            query["deleted_at"] = None
            if purpose == cls.ACTIVATION:
                query.update({
                    "is_active": False,
                    "status": "PENDING_ACTIVATION"
                })
            else:
                query.update({
                    "is_active": True,
                    "status": {"$nin": ["DELETED", "INACTIVE", "PENDING_ACTIVATION"]}
                })
        else:
            query["is_active"] = True

        update_fields = {
            "password_hash": password_hash,
            "password_changed_at": now
        }
        if purpose == cls.ACTIVATION:
            update_fields.update({
                "status": "ACTIVE",
                "is_active": True,
                "activated_at": now
            })
        update_pipeline = [{
            "$set": {
                **{
                    key: {"$literal": value} if key == "password_hash" else value
                    for key, value in update_fields.items()
                },
                "token_version": {
                    "$add": [{"$ifNull": ["$token_version", 1]}, 1]
                }
            }
        }]
        updated_account = collection.find_one_and_update(
            query,
            update_pipeline,
            return_document=ReturnDocument.AFTER
        )
        if not updated_account:
            cls._collection().delete_many({"account_id": account["account_id"]})
            raise OTPServiceError("This account is no longer active", status_code=403)

        cls._collection().delete_many({"account_id": account["account_id"]})
        event_type = (
            "ACCOUNT_ACTIVATED"
            if purpose == cls.ACTIVATION
            else "PASSWORD_RESET_COMPLETED"
        )
        cls._write_audit(
            event_type,
            account,
            None,
            actor_id=account["account_id"],
            actor_name=account["name"],
            actor_email=account["email"],
            actor_role_label=cls._actor_role_label(account),
            purpose=purpose
        )
        return {
            "success": True,
            "message": (
                "Account activated. You can now sign in."
                if purpose == cls.ACTIVATION
                else "Password reset successfully. You can now sign in."
            )
        }

    @classmethod
    def send_email(cls, encrypted_payload, provider):
        environment = str(current_app.config.get("APP_ENV", "development")).strip().lower()
        provider_name = str(provider).strip().lower()
        if environment == "production" and provider_name not in {
            "sendgrid", "ses", "amazon_ses", "smtp"
        }:
            raise OTPServiceError(
                "A real platform email provider is required in production",
                status_code=503
            )

        payload = cls.decrypt_email_payload(encrypted_payload)
        adapter = AdapterRegistry.get_adapter(
            provider=provider_name,
            channel="email",
            organization_id=None
        )
        if payload["purpose"] == cls.ACTIVATION:
            subject = "Activate your SenderX account"
            heading = "Activate your account"
        else:
            subject = "Reset your SenderX password"
            heading = "Reset your password"
        code = payload["code"]
        html = (
            "<html><body>"
            f"<h2>{heading}</h2>"
            "<p>Use this verification code to continue:</p>"
            f"<p style=\"font-size:24px;font-weight:bold;letter-spacing:4px\">{code}</p>"
            "<p>This code expires in 10 minutes.</p>"
            "<p>If you did not request this, ignore this email.</p>"
            "</body></html>"
        )
        result = adapter.send({
            "recipient": payload["email"],
            "data": {
                "subject": subject,
                "message": (
                    f"{heading}. Your code is {code}. "
                    "It expires in 10 minutes. "
                    "If you did not request this, ignore this email."
                ),
                "html": html
            }
        })
        if not result.get("success"):
            raise RuntimeError("Authentication email provider did not accept the message")
