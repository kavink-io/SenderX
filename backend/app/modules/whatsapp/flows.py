"""Tenant-scoped Meta WhatsApp Flows management and encrypted data exchange."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import jwt
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import current_app

from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.whatsapp.encryption import WhatsAppEncryption, WhatsAppEncryptionError
from app.modules.whatsapp.meta_client import MetaWhatsAppClient
from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
from app.modules.whatsapp.service import PlatformSettingsService, WhatsAppIntegrationService


class WhatsAppFlowService:
    COLLECTION = "whatsapp_flows"
    RESPONSE_COLLECTION = "whatsapp_flow_responses"
    EXCHANGE_COLLECTION = "whatsapp_flow_exchange_requests"
    CATEGORIES = {"SIGN_UP", "SIGN_IN", "APPOINTMENT_BOOKING", "LEAD_GENERATION", "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "OTHER"}

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @classmethod
    def _exchange_collection(cls):
        return current_app.mongo_db[cls.EXCHANGE_COLLECTION]

    @classmethod
    def _response_collection(cls):
        return current_app.mongo_db[cls.RESPONSE_COLLECTION]

    @classmethod
    def store_completion(cls, organization_id, integration_id, provider_message_id, response):
        """Store Flow completion values encrypted, separately from webhook metadata."""
        from app.modules.whatsapp.encryption import WhatsAppEncryption

        serialized = json.dumps(response, separators=(",", ":"), allow_nan=False)
        ciphertext, key_version = WhatsAppEncryption.encrypt_secret(serialized)
        try:
            retention_days = int(os.getenv("WHATSAPP_FLOW_RESPONSE_RETENTION_DAYS", "90"))
        except (TypeError, ValueError) as exc:
            raise ValueError("WHATSAPP_FLOW_RESPONSE_RETENTION_DAYS must be an integer") from exc
        if retention_days < 1 or retention_days > 3650:
            raise ValueError("WHATSAPP_FLOW_RESPONSE_RETENTION_DAYS must be between 1 and 3650")
        now = datetime.now(timezone.utc)
        doc = {
            "_id": hashlib.sha256(f"{organization_id}:{integration_id}:{provider_message_id}".encode()).hexdigest(),
            "organization_id": organization_id,
            "integration_id": integration_id,
            "provider_message_id": provider_message_id,
            "encrypted_response": ciphertext,
            "encryption_key_version": key_version,
            "created_at": now,
            "expires_at": now + timedelta(days=retention_days),
            "storage_version": 1,
        }
        collection = cls._response_collection()
        try:
            collection.insert_one(doc)
        except Exception as exc:
            from pymongo.errors import DuplicateKeyError
            if not isinstance(exc, DuplicateKeyError):
                raise
            existing = collection.find_one({"_id": doc["_id"]}, {"_id": 0, "organization_id": 1, "integration_id": 1})
            if not existing or existing.get("organization_id") != organization_id or existing.get("integration_id") != integration_id:
                raise ValueError("Flow completion identity conflicts with another tenant") from exc

    @classmethod
    def get_completion(cls, organization_id, integration_id, provider_message_id):
        cls._integration(organization_id, integration_id)
        record = cls._response_collection().find_one({
            "organization_id": organization_id,
            "integration_id": integration_id,
            "provider_message_id": provider_message_id,
        }, {"_id": 0})
        if not record:
            return None
        plaintext = WhatsAppEncryption.decrypt_secret(record["encrypted_response"])
        return {
            "provider_message_id": provider_message_id,
            "response": json.loads(plaintext),
            "created_at": record.get("created_at"),
            "expires_at": record.get("expires_at"),
        }

    @classmethod
    def delete_completion(cls, organization_id, integration_id, provider_message_id):
        cls._integration(organization_id, integration_id)
        result = cls._response_collection().delete_one({
            "organization_id": organization_id,
            "integration_id": integration_id,
            "provider_message_id": provider_message_id,
        })
        return bool(result.deleted_count)

    @staticmethod
    def _integration(organization_id, integration_id):
        integration = WhatsAppIntegrationRepository.find_by_id(integration_id, organization_id, include_deleted=False)
        if not integration or integration.get("status") != "CONNECTED":
            raise ValueError("Connected WhatsApp integration not found for this organization")
        return integration

    @classmethod
    def _credentials(cls, organization_id, integration_id):
        integration = cls._integration(organization_id, integration_id)
        credentials = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
            organization_id=organization_id, integration_id=integration_id
        )
        client = MetaWhatsAppClient(graph_api_version=credentials.get("graph_api_version"))
        return integration, credentials, client

    @staticmethod
    def _validate_https_url(value):
        parsed = urlsplit(value or "")
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Flow endpoint_uri must be an absolute HTTPS URL without credentials, query, or fragment")
        return value

    @staticmethod
    def _validate_handlers(handlers):
        if not isinstance(handlers, dict) or not handlers:
            raise ValueError("Endpoint-backed Flows require explicit endpoint_handlers")
        try:
            encoded = json.dumps(handlers, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("endpoint_handlers must contain only JSON values") from exc
        if len(encoded.encode("utf-8")) > 256 * 1024:
            raise ValueError("endpoint_handlers cannot exceed 256 KB")
        for key, response in handlers.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(response, dict):
                raise ValueError("Each endpoint handler must map an action to a response object")
            if not isinstance(response.get("screen"), str) or not response["screen"].strip() or not isinstance(response.get("data"), dict):
                raise ValueError("Each endpoint handler response requires a screen and data object")
        return handlers

    @staticmethod
    def _validate_flow_json(value):
        if not isinstance(value, dict) or not isinstance(value.get("screens"), list) or not value["screens"]:
            raise ValueError("flow_json must be a Flow JSON object containing at least one screen")
        version = value.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("flow_json requires a version string")
        data_api_version = value.get("data_api_version")
        if data_api_version is not None and data_api_version not in ("3.0", "4.0"):
            raise ValueError("Flow data_api_version must be '3.0' or '4.0'")
        return value

    @classmethod
    def _audit(cls, organization_id, integration_id, flow_id, action, actor=None, details=None):
        actor = actor or {}
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type=f"WHATSAPP_FLOW_{action.upper()}",
            actor_id=actor.get("user_id") or actor.get("admin_id"),
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            target_id=flow_id,
            target_type="WHATSAPP_FLOW",
            action_label=f"WhatsApp Flow {action}",
            summary=f"WhatsApp Flow {action}: {flow_id}",
            details={"integration_id": integration_id, **(details or {})},
        )

    @classmethod
    def list_flows(cls, organization_id, integration_id):
        cls._integration(organization_id, integration_id)
        return list(cls._collection().find(
            {"organization_id": organization_id, "integration_id": integration_id}, {"_id": 0, "endpoint_handlers": 0}
        ).sort("created_at", -1))

    @classmethod
    def get_flow(cls, organization_id, integration_id, flow_id):
        cls._integration(organization_id, integration_id)
        return cls._collection().find_one(
            {"organization_id": organization_id, "integration_id": integration_id, "flow_id": str(flow_id)},
            {"_id": 0, "endpoint_handlers": 0},
        )

    @classmethod
    def create_flow(cls, organization_id, integration_id, payload, actor=None):
        integration, credentials, client = cls._credentials(organization_id, integration_id)
        name = payload.get("name")
        categories = payload.get("categories")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
            raise ValueError("Flow name must be 1-60 characters")
        if not isinstance(categories, list) or not categories or any(c not in cls.CATEGORIES for c in categories):
            raise ValueError("Flow requires one or more supported Meta categories")
        flow_json = payload.get("flow_json")
        if flow_json is not None:
            flow_json = cls._validate_flow_json(flow_json)
        endpoint_enabled = bool(payload.get("endpoint_enabled", False))
        endpoint_uri = None
        handlers = payload.get("endpoint_handlers") or {}
        if endpoint_enabled:
            if payload.get("publish") is True:
                raise ValueError("Create endpoint-backed Flows as drafts, configure their endpoint, then publish")
            base_url = os.getenv("WHATSAPP_FLOW_ENDPOINT_BASE_URL", "").rstrip("/")
            if not base_url:
                raise ValueError("WHATSAPP_FLOW_ENDPOINT_BASE_URL must be configured for endpoint-backed Flows")
            cls._validate_https_url(base_url)
            handlers = cls._validate_handlers(handlers)
            if integration.get("flow_public_key_status") != "REGISTERED" or not integration.get("encrypted_flow_private_key"):
                raise ValueError("Register the Flow encryption public key for this integration before enabling an endpoint")
            if not PlatformSettingsService.get_meta_settings(decrypt=True).get("meta_app_secret"):
                raise ValueError("Meta App Secret must be configured before enabling Flow endpoints")
            if flow_json is None or flow_json.get("data_api_version") not in ("3.0", "4.0"):
                raise ValueError("Endpoint-backed Flow JSON must declare data_api_version '3.0' or '4.0'")
            endpoint_uri = f"{base_url}/api/v1/whatsapp/flows/{integration_id}/{payload.get('flow_id', 'pending')}/data"
        request_data = {
            "name": name.strip(),
            "categories": json.dumps(categories),
        }
        if flow_json is not None:
            request_data["flow_json"] = json.dumps(flow_json, separators=(",", ":"))
        if payload.get("publish") is True:
            request_data["publish"] = "true"
        if payload.get("clone_flow_id"):
            request_data["clone_flow_id"] = str(payload["clone_flow_id"])
        result = client.request_graph("POST", f"{integration['waba_id']}/flows", credentials["access_token"], data=request_data)
        flow_id = str(result.get("id") or "").strip()
        if not flow_id:
            raise RuntimeError("Meta did not return a Flow ID")
        # Endpoint URI needs the provider-assigned Flow ID; attach it after creation.
        if endpoint_uri:
            endpoint_uri = f"{os.getenv('WHATSAPP_FLOW_ENDPOINT_BASE_URL').rstrip('/')}/api/v1/whatsapp/flows/{integration_id}/{flow_id}/data"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "organization_id": organization_id, "integration_id": integration_id, "waba_id": integration["waba_id"],
            "flow_id": flow_id, "name": name.strip(), "categories": categories,
            "status": "PUBLISHED" if payload.get("publish") else "DRAFT",
            "endpoint_enabled": endpoint_enabled, "endpoint_uri": endpoint_uri,
            "endpoint_handlers": handlers if endpoint_enabled else {},
            "endpoint_setup_status": "PENDING" if endpoint_enabled else None,
            "created_at": now, "updated_at": now,
        }
        cls._collection().insert_one(doc)
        if endpoint_uri:
            try:
                client.request_graph("POST", flow_id, credentials["access_token"], data={"endpoint_uri": endpoint_uri})
                cls._collection().update_one({"organization_id": organization_id, "integration_id": integration_id, "flow_id": flow_id}, {"$set": {"endpoint_setup_status": "CONFIGURED"}})
            except Exception:
                cls._collection().update_one({"organization_id": organization_id, "integration_id": integration_id, "flow_id": flow_id}, {"$set": {"endpoint_setup_status": "FAILED"}})
                raise
        cls._audit(organization_id, integration_id, flow_id, "CREATED", actor, {"status": doc["status"]})
        return cls.get_flow(organization_id, integration_id, flow_id)

    @classmethod
    def update_flow(cls, organization_id, integration_id, flow_id, payload, actor=None):
        integration, credentials, client = cls._credentials(organization_id, integration_id)
        query = {"organization_id": organization_id, "integration_id": integration_id, "flow_id": str(flow_id)}
        existing = cls._collection().find_one(query)
        if not existing:
            raise LookupError("WhatsApp Flow not found for this organization")
        fields = {}
        if "name" in payload:
            if not isinstance(payload["name"], str) or not payload["name"].strip() or len(payload["name"].strip()) > 60:
                raise ValueError("Flow name must be 1-60 characters")
            fields["name"] = payload["name"].strip()
        if "categories" in payload:
            cats = payload["categories"]
            if not isinstance(cats, list) or not cats or any(c not in cls.CATEGORIES for c in cats):
                raise ValueError("Flow requires one or more supported Meta categories")
            fields["categories"] = cats
        if "endpoint_handlers" in payload:
            if not existing.get("endpoint_enabled"):
                raise ValueError("endpoint_handlers can only be updated for an enabled Flow and must be an object")
            fields["endpoint_handlers"] = cls._validate_handlers(payload["endpoint_handlers"])
        if "flow_json" in payload:
            flow_json = cls._validate_flow_json(payload["flow_json"])
            file_bytes = json.dumps(flow_json, separators=(",", ":")).encode("utf-8")
            client.request_graph(
                "POST", f"{flow_id}/assets", credentials["access_token"],
                data={"name": "flow.json", "asset_type": "FLOW_JSON"},
                files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
            )
            fields["flow_json_sha256"] = hashlib.sha256(file_bytes).hexdigest()
        if fields:
            client.request_graph("POST", str(flow_id), credentials["access_token"], data={k: v if isinstance(v, str) else json.dumps(v) for k, v in fields.items() if k in ("name", "categories")}) if any(k in fields for k in ("name", "categories")) else None
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            cls._collection().update_one(query, {"$set": fields})
        cls._audit(organization_id, integration_id, flow_id, "UPDATED", actor, {"flow_json_updated": "flow_json_sha256" in fields})
        return cls.get_flow(organization_id, integration_id, flow_id)

    @classmethod
    def publish_flow(cls, organization_id, integration_id, flow_id, actor=None):
        integration, credentials, client = cls._credentials(organization_id, integration_id)
        query = {"organization_id": organization_id, "integration_id": integration_id, "flow_id": str(flow_id)}
        if not cls._collection().find_one(query):
            raise LookupError("WhatsApp Flow not found for this organization")
        result = client.request_graph("POST", f"{flow_id}/publish", credentials["access_token"])
        cls._collection().update_one(query, {"$set": {"status": "PUBLISHED", "updated_at": datetime.now(timezone.utc).isoformat()}})
        cls._audit(organization_id, integration_id, flow_id, "PUBLISHED", actor)
        return {"success": result.get("success", True), "flow": cls.get_flow(organization_id, integration_id, flow_id)}

    @classmethod
    def deprecate_flow(cls, organization_id, integration_id, flow_id, actor=None):
        integration, credentials, client = cls._credentials(organization_id, integration_id)
        query = {"organization_id": organization_id, "integration_id": integration_id, "flow_id": str(flow_id)}
        if not cls._collection().find_one(query):
            raise LookupError("WhatsApp Flow not found for this organization")
        client.request_graph("DELETE", f"{flow_id}/deprecate", credentials["access_token"])
        cls._collection().update_one(query, {"$set": {"status": "DEPRECATED", "updated_at": datetime.now(timezone.utc).isoformat()}})
        cls._audit(organization_id, integration_id, flow_id, "DEPRECATED", actor)
        return cls.get_flow(organization_id, integration_id, flow_id)

    @classmethod
    def setup_encryption_key(cls, organization_id, integration_id, actor=None):
        integration, credentials, client = cls._credentials(organization_id, integration_id)
        private_pem, public_pem = WhatsAppEncryption.generate_flow_key_pair()
        encrypted, version = WhatsAppEncryption.encrypt_secret(private_pem)
        retained_keys = list(integration.get("encrypted_flow_private_keys") or [])
        existing_ciphertext = integration.get("encrypted_flow_private_key")
        if existing_ciphertext:
            retained_keys.insert(0, {
                "ciphertext": existing_ciphertext,
                "key_version": integration.get("flow_key_version"),
                "public_key_fingerprint": integration.get("flow_public_key_fingerprint"),
            })
        # Persist before provider setup so a network interruption cannot lose the private half.
        WhatsAppIntegrationRepository.update(integration_id, organization_id, {
            "encrypted_flow_private_key": encrypted, "flow_key_version": version,
            "encrypted_flow_private_keys": retained_keys,
            "flow_public_key_fingerprint": hashlib.sha256(public_pem.encode()).hexdigest(),
            "flow_public_key_status": "PENDING",
        })
        client.request_graph("POST", f"{integration['phone_number_id']}/whatsapp_business_encryption", credentials["access_token"], json_body={"business_public_key": public_pem})
        WhatsAppIntegrationRepository.update(integration_id, organization_id, {"flow_public_key_status": "REGISTERED"})
        cls._audit(organization_id, integration_id, integration_id, "PUBLIC_KEY_REGISTERED", actor)
        return {"registered": True, "public_key_fingerprint": hashlib.sha256(public_pem.encode()).hexdigest()}

    @classmethod
    def exchange(cls, integration_id, flow_id, raw_body, signature):
        """Verify, decrypt, dispatch to the flow-specific configured handler, then encrypt."""
        integration = WhatsAppIntegrationRepository.find_by_id(integration_id, include_deleted=False)
        if not integration or integration.get("status") != "CONNECTED":
            return "", 404
        flow = cls._collection().find_one({"organization_id": integration.get("organization_id"), "integration_id": integration_id, "flow_id": str(flow_id)})
        if not flow or not flow.get("endpoint_enabled") or not integration.get("encrypted_flow_private_key"):
            return "", 404
        settings = PlatformSettingsService.get_meta_settings(decrypt=True)
        secret = settings.get("meta_app_secret")
        if not secret:
            return "", 503
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            return "", 401
        # Fast replay lookup follows raw-body signature verification and is
        # scoped to the already-resolved tenant integration and Flow.
        request_digest = hashlib.sha256(raw_body).hexdigest()
        request_id = hashlib.sha256(
            f"{integration['organization_id']}:{integration_id}:{flow_id}:{request_digest}".encode("utf-8")
        ).hexdigest()
        exchange_collection = cls._exchange_collection()
        existing = exchange_collection.find_one({
            "_id": request_id,
            "organization_id": integration["organization_id"],
            "integration_id": integration_id,
            "flow_id": str(flow_id),
        })
        if existing:
            if existing.get("state") == "COMPLETED" and existing.get("encrypted_response"):
                return existing["encrypted_response"], 200
            return "", 503
        try:
            encrypted_request = json.loads(raw_body.decode("utf-8"))
            encrypted_keys = [integration["encrypted_flow_private_key"]]
            encrypted_keys.extend(
                item.get("ciphertext") for item in integration.get("encrypted_flow_private_keys", [])
                if isinstance(item, dict) and item.get("ciphertext")
            )
            decryption_error = None
            for encrypted_private_key in encrypted_keys:
                try:
                    private_pem = WhatsAppEncryption.decrypt_secret(encrypted_private_key)
                    request_data, aes_key, iv = WhatsAppEncryption.decrypt_flow_request(private_pem, encrypted_request)
                    break
                except WhatsAppEncryptionError as exc:
                    decryption_error = exc
            else:
                raise decryption_error or WhatsAppEncryptionError("WhatsApp Flow request decryption failed")
            token_signature = request_data.get("flow_token_signature")
            if token_signature:
                claims = jwt.decode(token_signature, secret, algorithms=["HS256"])
                if claims.get("flow_token") != request_data.get("flow_token"):
                    return "", 401

            # Meta has no documented unique request ID, so atomically reserve
            # this exact signed request after validation and before handlers.
            try:
                exchange_collection.insert_one({
                    "_id": request_id,
                    "organization_id": integration["organization_id"],
                    "integration_id": integration_id,
                    "flow_id": str(flow_id),
                    "request_sha256": request_digest,
                    "state": "PROCESSING",
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as exc:
                from pymongo.errors import DuplicateKeyError
                if not isinstance(exc, DuplicateKeyError):
                    raise
                existing = exchange_collection.find_one({
                    "_id": request_id,
                    "organization_id": integration["organization_id"],
                    "integration_id": integration_id,
                    "flow_id": str(flow_id),
                })
                if existing and existing.get("state") == "COMPLETED" and existing.get("encrypted_response"):
                    return existing["encrypted_response"], 200
                # A concurrent or interrupted request stays closed to avoid
                # repeating work. A concurrent retry can succeed from cache.
                return "", 503
            action = request_data.get("action")
            if action == "ping":
                response = {"data": {"status": "active"}}
            elif action in ("data_exchange", "INIT") and isinstance(request_data.get("data"), dict) and request_data["data"].get("error"):
                response = {"data": {"acknowledged": True}}
            else:
                handlers = flow.get("endpoint_handlers", {})
                handler_key = f"{request_data.get('screen', '')}:{action}"
                response = handlers.get(handler_key) or handlers.get(str(action))
                if not isinstance(response, dict) or not isinstance(response.get("screen"), str) or not isinstance(response.get("data"), dict):
                    exchange_collection.delete_one({
                        "_id": request_id,
                        "organization_id": integration["organization_id"],
                        "integration_id": integration_id,
                    })
                    return "", 400
            encrypted_response = WhatsAppEncryption.encrypt_flow_response(response, aes_key, iv)
            exchange_collection.update_one(
                {"_id": request_id, "organization_id": integration["organization_id"], "integration_id": integration_id},
                {"$set": {"state": "COMPLETED", "encrypted_response": encrypted_response, "completed_at": datetime.now(timezone.utc)}},
            )
            return encrypted_response, 200
        except jwt.InvalidTokenError:
            return "", 401
        except (WhatsAppEncryptionError, ValueError, KeyError, UnicodeDecodeError):
            # Decrypted Flow data and cryptographic details are deliberately never logged.
            return "", 421
