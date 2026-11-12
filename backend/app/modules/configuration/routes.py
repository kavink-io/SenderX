from flask import Blueprint, jsonify

from app.modules.configuration.service import ConfigurationService


configuration_bp = Blueprint(
    "configuration",
    __name__
)


@configuration_bp.route("/", methods=["GET"])
def get_configuration():

    config = ConfigurationService.get_public_config()

    return jsonify({
        "success": True,
        "message": "Configuration retrieved successfully",
        "data": config
    }), 200