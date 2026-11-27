
from flask import Blueprint, request, jsonify, g

from app.adapters.errors import ProviderResolutionError
from app.modules.provider_config.service import ProviderConfigService
from app.modules.auth.decorators import require_roles, require_permissions


provider_config_bp = Blueprint(
    "provider_config",
    __name__
)


@provider_config_bp.route("/", methods=["POST"])
@require_roles("SUPER_ADMIN")
def save_provider_config():

    data = request.get_json(silent=True) or {}

    provider = data.get("provider")
    credentials = data.get("credentials")

    if (
        not provider
        or not isinstance(credentials, dict)
        or not credentials
    ):
        return jsonify({
            "success": False,
            "message": "Provider and credentials are required"
        }), 400

    try:
        ProviderConfigService.save_configuration(
            provider,
            credentials
        )

        return jsonify({
            "success": True,
            "message": "Provider configuration saved securely"
        }), 201

    except ProviderResolutionError as error:
        return jsonify(error.to_dict()), error.status_code

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    except Exception:
        return jsonify({
            "success": False,
            "message": "Could not save provider configuration"
        }), 500


@provider_config_bp.route("/", methods=["GET"])
@require_roles("SUPER_ADMIN")
def get_provider_configs():

    try:
        provider = request.args.get("provider")

        if provider:
            config = ProviderConfigService.get_configuration_status(
                provider
            )

            if not config:
                return jsonify({
                    "success": False,
                    "message": "Provider configuration not found"
                }), 404

            return jsonify({
                "success": True,
                "data": config
            }), 200

        configs = ProviderConfigService.get_all_configuration_statuses()

        return jsonify({
            "success": True,
            "count": len(configs),
            "data": configs
        }), 200

    except Exception:
        return jsonify({
            "success": False,
            "message": "Could not retrieve provider configurations"
        }), 500


# ======================================================
# ORGANIZATION-SCOPED PROVIDER CONFIG ENDPOINTS
# ======================================================

@provider_config_bp.route("/organization", methods=["POST"])
@require_permissions("organization:providers:manage")
def save_organization_provider_config():

    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    credentials = data.get("credentials")

    if not provider or not isinstance(credentials, dict) or not credentials:
        return jsonify({
            "success": False,
            "message": "Provider and credentials are required"
        }), 400

    organization_id = g.current_organization["organization_id"]

    try:
        ProviderConfigService.save_configuration(
            provider=provider,
            credentials=credentials,
            organization_id=organization_id
        )

        return jsonify({
            "success": True,
            "message": "Organization provider configuration saved securely",
            "data": {
                "provider": provider,
                "organization_id": organization_id,
                "configured": True
            }
        }), 201

    except ProviderResolutionError as error:
        return jsonify(error.to_dict()), error.status_code
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except Exception:
        return jsonify({"success": False, "message": "Could not save provider configuration"}), 500


@provider_config_bp.route("/organization/status", methods=["PATCH", "POST"])
@require_permissions("organization:providers:manage")
def set_organization_provider_status():
    """Activate or deactivate an existing organization provider configuration."""
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    is_active = data.get("is_active")
    if not provider or not isinstance(is_active, bool):
        return jsonify({
            "success": False,
            "message": "'provider' and boolean 'is_active' are required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    try:
        ProviderConfigService.set_configuration_active_state(
            provider=provider,
            is_active=is_active,
            organization_id=organization_id,
        )
        return jsonify({
            "success": True,
            "message": f"Organization provider '{provider}' {'activated' if is_active else 'deactivated'}",
            "data": {
                "provider": provider.lower().strip(),
                "organization_id": organization_id,
                "configured": is_active,
                "status": "ACTIVE" if is_active else "INACTIVE",
            },
        }), 200
    except ProviderResolutionError as err:
        return jsonify(err.to_dict()), err.status_code
    except Exception:
        return jsonify({"success": False, "message": "Could not update provider configuration status"}), 500


@provider_config_bp.route("/organization", methods=["GET"])
@require_permissions("organization:providers:read")
def get_organization_provider_configs():

    organization_id = g.current_organization["organization_id"]
    provider = request.args.get("provider")

    try:
        if provider:
            config = ProviderConfigService.get_configuration_status(
                provider=provider,
                organization_id=organization_id
            )
            if not config:
                return jsonify({"success": False, "message": "Provider configuration not found"}), 404
            return jsonify({"success": True, "data": config}), 200

        configs = ProviderConfigService.get_all_configuration_statuses(organization_id=organization_id)
        return jsonify({
            "success": True,
            "count": len(configs),
            "data": configs
        }), 200

    except Exception:
        return jsonify({"success": False, "message": "Could not retrieve provider configurations"}), 500


@provider_config_bp.route("/validate", methods=["POST"])
@require_roles("SUPER_ADMIN")
def validate_platform_provider_config():
    """Validate provider credentials format and presence without saving."""
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    credentials = data.get("credentials")

    try:
        ProviderConfigService.validate_credentials(provider, credentials)
        return jsonify({
            "success": True,
            "message": f"Provider configuration structure for '{provider}' is valid"
        }), 200
    except ValueError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as err:
        return jsonify({"success": False, "message": f"Validation failed: {str(err)}"}), 500


@provider_config_bp.route("/organization/validate", methods=["POST"])
@require_permissions("organization:providers:manage")
def validate_organization_provider_config():
    """Validate organization provider credentials format and presence."""
    data = request.get_json(silent=True) or {}
    provider = data.get("provider")
    credentials = data.get("credentials")

    try:
        ProviderConfigService.validate_credentials(provider, credentials)
        return jsonify({
            "success": True,
            "message": f"Organization provider configuration structure for '{provider}' is valid"
        }), 200
    except ValueError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as err:
        return jsonify({"success": False, "message": f"Validation failed: {str(err)}"}), 500


# ======================================================
# MICROSOFT TEAMS DELEGATED OAUTH 2.0 ROUTES
# ======================================================

@provider_config_bp.route("/teams/connect", methods=["GET"])
@require_permissions("organization:providers:manage")
def get_teams_connect_url():
    """
    Generate Microsoft Entra ID authorization URL for connecting
    the organization's Teams account with delegated permissions.
    """
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None
    redirect_uri = request.args.get("redirect_uri")

    try:
        result = ProviderConfigService.get_teams_authorization_url(
            organization_id=organization_id,
            redirect_uri=redirect_uri,
            user_id=user_id
        )
        return jsonify(result), 200
    except ValueError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as err:
        return jsonify({"success": False, "message": f"Could not generate Teams connect URL: {str(err)}"}), 500


@provider_config_bp.route("/teams/oauth/callback", methods=["GET"])
def teams_oauth_callback():
    """
    OAuth 2.0 callback endpoint invoked by Microsoft Entra ID.
    Validates state parameter, exchanges code for access & refresh tokens.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    error_desc = request.args.get("error_description")

    if error:
        return jsonify({
            "success": False,
            "error": error,
            "message": error_desc or "Microsoft authorization denied"
        }), 400

    result = ProviderConfigService.handle_teams_oauth_callback(
        code=code,
        state=state
    )
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@provider_config_bp.route("/teams/oauth/exchange", methods=["POST"])
@require_permissions("organization:providers:manage")
def teams_oauth_exchange():
    """
    Manual/frontend token exchange endpoint for SPA authorization code grant.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    state = data.get("state")
    redirect_uri = data.get("redirect_uri")

    result = ProviderConfigService.handle_teams_oauth_callback(
        code=code,
        state=state,
        redirect_uri=redirect_uri
    )
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@provider_config_bp.route("/teams/disconnect", methods=["POST", "DELETE"])
@require_permissions("organization:providers:manage")
def disconnect_teams():
    """Disconnect Microsoft Teams integration for the organization."""
    organization_id = g.current_organization["organization_id"]
    ProviderConfigService.disconnect_provider("teams", organization_id=organization_id)
    return jsonify({
        "success": True,
        "message": "Microsoft Teams disconnected successfully for organization"
    }), 200


