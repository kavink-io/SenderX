
from flask import Blueprint, request, jsonify

from app.modules.provider_config.service import ProviderConfigService


provider_config_bp = Blueprint(
    "provider_config",
    __name__
)


@provider_config_bp.route("/", methods=["POST"])
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
