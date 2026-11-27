"""
SenderX WhatsApp Integration and Platform Settings Routes
Provides REST API endpoints for:
- Organization-specific WhatsApp Cloud API integration lifecycle management.
- Centralized encrypted Meta platform settings management for Platform Admins.
"""

from flask import Blueprint, current_app, jsonify, request, g

from app.modules.auth.decorators import (
    require_permissions,
    require_roles,
    require_organization_wide_scope,
)
from app.modules.whatsapp.meta_client import (
    WhatsAppVerificationError,
    WhatsAppVerificationErrorCode,
)
from app.modules.whatsapp.service import (
    WhatsAppIntegrationService,
    PlatformSettingsService,
)
from app.modules.whatsapp.flows import WhatsAppFlowService

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.route("/integrations/<integration_id>/flows", methods=["GET", "POST"])
@require_permissions("organization:providers:manage")
def manage_flows(integration_id):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)
    try:
        if request.method == "GET":
            items = WhatsAppFlowService.list_flows(organization_id, integration_id)
            return jsonify({"success": True, "data": items, "count": len(items)}), 200
        flow = WhatsAppFlowService.create_flow(organization_id, integration_id, request.get_json(silent=True) or {}, actor)
        return jsonify({"success": True, "data": flow}), 201
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        return jsonify({"success": False, "message": "WhatsApp Flow operation failed"}), 502


@whatsapp_bp.route("/integrations/<integration_id>/flows/<flow_id>", methods=["GET", "PATCH"])
@require_permissions("organization:providers:manage")
def flow_detail(integration_id, flow_id):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    try:
        if request.method == "GET":
            flow = WhatsAppFlowService.get_flow(organization_id, integration_id, flow_id)
            if not flow:
                return jsonify({"success": False, "message": "WhatsApp Flow not found"}), 404
            return jsonify({"success": True, "data": flow}), 200
        flow = WhatsAppFlowService.update_flow(
            organization_id, integration_id, flow_id, request.get_json(silent=True) or {}, getattr(g, "current_user", None)
        )
        return jsonify({"success": True, "data": flow}), 200
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        return jsonify({"success": False, "message": "WhatsApp Flow operation failed"}), 502


@whatsapp_bp.route("/integrations/<integration_id>/flows/<flow_id>/publish", methods=["POST"])
@require_permissions("organization:providers:manage")
def publish_flow(integration_id, flow_id):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    try:
        result = WhatsAppFlowService.publish_flow(
            g.current_organization["organization_id"], integration_id, flow_id, getattr(g, "current_user", None)
        )
        return jsonify({"success": True, "data": result}), 200
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception:
        return jsonify({"success": False, "message": "WhatsApp Flow publish failed"}), 502


@whatsapp_bp.route("/integrations/<integration_id>/flows/<flow_id>/deprecate", methods=["POST"])
@require_permissions("organization:providers:manage")
def deprecate_flow(integration_id, flow_id):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    try:
        flow = WhatsAppFlowService.deprecate_flow(
            g.current_organization["organization_id"], integration_id, flow_id, getattr(g, "current_user", None)
        )
        return jsonify({"success": True, "data": flow}), 200
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception:
        return jsonify({"success": False, "message": "WhatsApp Flow deprecation failed"}), 502


@whatsapp_bp.route("/integrations/<integration_id>/flows/encryption-key", methods=["POST"])
@require_permissions("organization:providers:manage")
def register_flow_encryption_key(integration_id):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    try:
        result = WhatsAppFlowService.setup_encryption_key(
            g.current_organization["organization_id"], integration_id, getattr(g, "current_user", None)
        )
        return jsonify({"success": True, "data": result}), 200
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        return jsonify({"success": False, "message": "Meta public-key registration failed"}), 502


@whatsapp_bp.route("/integrations/<integration_id>/flow-completions/<provider_message_id>", methods=["GET"])
@require_permissions("organization:messages:read")
def flow_completion(integration_id, provider_message_id):
    organization_id = g.current_organization["organization_id"]
    try:
        completion = WhatsAppFlowService.get_completion(organization_id, integration_id, provider_message_id)
        if completion is None:
            return jsonify({"success": False, "message": "Flow completion not found"}), 404
        return jsonify({"success": True, "data": completion}), 200
    except ValueError:
        return jsonify({"success": False, "message": "Flow integration not found for this organization"}), 404
    except Exception:
        return jsonify({"success": False, "message": "Flow completion operation failed"}), 500


@whatsapp_bp.route("/integrations/<integration_id>/flow-completions/<provider_message_id>", methods=["DELETE"])
@require_permissions("organization:messages:manage")
def delete_flow_completion(integration_id, provider_message_id):
    organization_id = g.current_organization["organization_id"]
    try:
        deleted = WhatsAppFlowService.delete_completion(organization_id, integration_id, provider_message_id)
        if not deleted:
            return jsonify({"success": False, "message": "Flow completion not found"}), 404
        return jsonify({"success": True, "message": "Flow completion deleted"}), 200
    except ValueError:
        return jsonify({"success": False, "message": "Flow integration not found for this organization"}), 404
    except Exception:
        return jsonify({"success": False, "message": "Flow completion operation failed"}), 500


@whatsapp_bp.route("/flows/<integration_id>/<flow_id>/data", methods=["POST"])
def flow_data_exchange(integration_id, flow_id):
    maximum_size = 10 * 1024 * 1024
    if request.content_length is not None and request.content_length > maximum_size:
        return "", 413
    raw_body = request.stream.read(maximum_size + 1)
    if len(raw_body) > maximum_size:
        return "", 413
    body, status = WhatsAppFlowService.exchange(
        integration_id, flow_id, raw_body, request.headers.get("X-Hub-Signature-256")
    )
    if status != 200:
        return "", status
    return body, 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}


# =========================================================================
# Organization WhatsApp Integrations (Multi-Tenant)
# =========================================================================

@whatsapp_bp.route("/integrations/connect", methods=["POST"])
@require_permissions("organization:providers:manage")
def connect_manual_integration():
    """
    Connect an organization WhatsApp Business Account manually using WABA ID,
    Phone Number ID, and Access Token verified against the real Meta Graph API.
    """
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        result = WhatsAppIntegrationService.connect_manual_integration(
            organization_id=organization_id,
            data=data,
            actor=actor
        )
        return jsonify({
            "success": True,
            "message": "WhatsApp Business Account connected and verified successfully",
            "data": result
        }), 201
    except WhatsAppVerificationError as e:
        status_code = 400
        if e.error_code == WhatsAppVerificationErrorCode.INVALID_CREDENTIALS:
            status_code = 401
        elif e.error_code == WhatsAppVerificationErrorCode.INSUFFICIENT_PERMISSIONS:
            status_code = 403
        elif e.error_code == WhatsAppVerificationErrorCode.PHONE_NUMBER_MISMATCH:
            status_code = 422
        elif e.error_code == WhatsAppVerificationErrorCode.META_API_UNAVAILABLE:
            status_code = 503
        return jsonify({
            "success": False,
            "message": e.message,
            "error_code": e.error_code.value,
            "meta_code": e.meta_code
        }), status_code
    except ValueError as e:
        msg = str(e)
        status_code = 409 if "already registered" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to connect WhatsApp Business Account")
        return jsonify({
            "success": False,
            "message": "Failed to connect WhatsApp Business Account"
        }), 500


@whatsapp_bp.route("/integrations", methods=["POST"])
@require_permissions("organization:providers:manage")
def create_integration():
    """Connect a new WhatsApp Business phone number for this organization."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        result = WhatsAppIntegrationService.create_integration(
            organization_id=organization_id,
            data=data,
            actor=actor
        )
        return jsonify({
            "success": True,
            "message": "WhatsApp integration created successfully",
            "data": result
        }), 201
    except ValueError as e:
        msg = str(e)
        status_code = 409 if "already registered" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to create WhatsApp integration")
        return jsonify({
            "success": False,
            "message": "Failed to create WhatsApp integration"
        }), 500


@whatsapp_bp.route("/integrations", methods=["GET"])
@require_permissions("organization:providers:read")
def list_integrations():
    """List all WhatsApp phone number integrations for this organization."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    status_filter = request.args.get("status")
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"

    try:
        items = WhatsAppIntegrationService.list_integrations(
            organization_id=organization_id,
            status=status_filter,
            include_deleted=include_deleted
        )
        return jsonify({
            "success": True,
            "data": items,
            "count": len(items)
        }), 200
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
    except Exception:
        current_app.logger.exception("Failed to list WhatsApp integrations")
        return jsonify({
            "success": False,
            "message": "Failed to list WhatsApp integrations"
        }), 500


@whatsapp_bp.route("/integrations/<integration_id>", methods=["GET"])
@require_permissions("organization:providers:read")
def get_integration(integration_id):
    """Retrieve details of a specific WhatsApp integration (strictly scoped to current org)."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]

    try:
        item = WhatsAppIntegrationService.get_integration(
            integration_id=integration_id,
            organization_id=organization_id
        )
        if not item:
            return jsonify({
                "success": False,
                "message": f"WhatsApp integration '{integration_id}' not found in your organization"
            }), 404

        return jsonify({
            "success": True,
            "data": item
        }), 200
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
    except Exception:
        current_app.logger.exception("Failed to retrieve WhatsApp integration")
        return jsonify({
            "success": False,
            "message": "Failed to retrieve WhatsApp integration"
        }), 500


@whatsapp_bp.route("/integrations/<integration_id>", methods=["PATCH"])
@require_permissions("organization:providers:manage")
def update_integration(integration_id):
    """Update metadata for an existing WhatsApp integration."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        item = WhatsAppIntegrationService.update_integration(
            integration_id=integration_id,
            organization_id=organization_id,
            data=data,
            actor=actor
        )
        return jsonify({
            "success": True,
            "message": "WhatsApp integration updated successfully",
            "data": item
        }), 200
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to update WhatsApp integration")
        return jsonify({
            "success": False,
            "message": "Failed to update WhatsApp integration"
        }), 500


@whatsapp_bp.route("/integrations/<integration_id>/rotate", methods=["POST"])
@require_permissions("organization:providers:manage")
def rotate_credentials(integration_id):
    """Rotate access token credentials for a WhatsApp integration."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        item = WhatsAppIntegrationService.rotate_credentials(
            integration_id=integration_id,
            organization_id=organization_id,
            data=data,
            actor=actor
        )
        return jsonify({
            "success": True,
            "message": "WhatsApp access token rotated successfully",
            "data": item
        }), 200
    except WhatsAppVerificationError as e:
        status_code = 401 if e.error_code == WhatsAppVerificationErrorCode.INVALID_CREDENTIALS else 400
        return jsonify({
            "success": False,
            "message": e.message,
            "error_code": e.error_code.value,
            "meta_code": e.meta_code
        }), status_code
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to rotate WhatsApp credentials")
        return jsonify({
            "success": False,
            "message": "Failed to rotate WhatsApp credentials"
        }), 500


@whatsapp_bp.route("/integrations/<integration_id>/verify", methods=["POST"])
@require_permissions("organization:providers:manage")
def verify_credential_status(integration_id):
    """Verify integrity and format of stored WhatsApp credentials without exposing token."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        status_info = WhatsAppIntegrationService.verify_credential_status(
            integration_id=integration_id,
            organization_id=organization_id,
            actor=actor
        )
        return jsonify({
            "success": True,
            "data": status_info
        }), 200
    except WhatsAppVerificationError as e:
        return jsonify({
            "success": False,
            "message": e.message,
            "error_code": e.error_code.value,
            "meta_code": e.meta_code
        }), 400
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to verify WhatsApp credentials")
        return jsonify({
            "success": False,
            "message": "Failed to verify WhatsApp credentials"
        }), 500


@whatsapp_bp.route("/integrations/<integration_id>", methods=["DELETE"])
@require_permissions("organization:providers:manage")
def disconnect_integration(integration_id):
    """Soft-delete / disconnect a WhatsApp integration."""
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    actor = getattr(g, "current_user", None)

    try:
        deleted = WhatsAppIntegrationService.disconnect_integration(
            integration_id=integration_id,
            organization_id=organization_id,
            actor=actor
        )
        if not deleted:
            return jsonify({
                "success": False,
                "message": f"WhatsApp integration '{integration_id}' not found or already disconnected"
            }), 404

        return jsonify({
            "success": True,
            "message": "WhatsApp integration disconnected successfully"
        }), 200
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 400
        return jsonify({
            "success": False,
            "message": msg
        }), status_code
    except Exception:
        current_app.logger.exception("Failed to disconnect WhatsApp integration")
        return jsonify({
            "success": False,
            "message": "Failed to disconnect WhatsApp integration"
        }), 500


# =========================================================================
# Centralized Meta Platform Settings (Platform Admin Only)
# =========================================================================

@whatsapp_bp.route("/platform-settings", methods=["GET"])
@require_roles("PLATFORM_ADMIN", "SUPER_ADMIN")
def get_platform_settings():
    """Retrieve centralized Meta App ID, Webhooks, and masked App Secret."""
    try:
        settings = PlatformSettingsService.get_meta_settings(decrypt=False)
        return jsonify({
            "success": True,
            "data": settings
        }), 200
    except Exception:
        current_app.logger.exception("Failed to retrieve platform settings")
        return jsonify({
            "success": False,
            "message": "Failed to retrieve platform settings"
        }), 500


@whatsapp_bp.route("/platform-settings", methods=["PUT"])
@require_roles("PLATFORM_ADMIN", "SUPER_ADMIN")
def update_platform_settings():
    """Update centralized Meta App ID, encrypted App Secret, and Webhook configuration."""
    data = request.get_json(silent=True) or {}
    actor = getattr(g, "current_admin", None)

    try:
        saved = PlatformSettingsService.save_meta_settings(data=data, actor=actor)
        return jsonify({
            "success": True,
            "message": "Platform Meta WhatsApp settings updated successfully",
            "data": saved
        }), 200
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
    except Exception:
        current_app.logger.exception("Failed to update platform settings")
        return jsonify({
            "success": False,
            "message": "Failed to update platform settings"
        }), 500
