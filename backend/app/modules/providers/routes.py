from flask import Blueprint, jsonify

from app.modules.providers.service import ProviderService


providers_bp = Blueprint("providers", __name__)


@providers_bp.route("/", methods=["GET"])
def get_providers():

    return jsonify({
        "success": True,
        "message": "Providers retrieved successfully",
        "data": ProviderService.get_all_providers()
    }), 200


@providers_bp.route("/<string:provider_name>", methods=["GET"])
def get_provider(provider_name):

    provider = ProviderService.get_provider(provider_name)

    if not provider:
        return jsonify({
            "success": False,
            "message": "Provider not found",
            "data": None
        }), 404

    return jsonify({
        "success": True,
        "message": "Provider retrieved successfully",
        "data": provider
    }), 200


@providers_bp.route("/channel/<string:channel_name>", methods=["GET"])
def get_channel_providers(channel_name):

    providers = ProviderService.get_providers_by_channel(
        channel_name
    )

    return jsonify({
        "success": True,
        "message": "Providers retrieved successfully",
        "data": providers
    }), 200