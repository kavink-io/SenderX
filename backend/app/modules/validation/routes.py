from flask import Blueprint, request, jsonify

from app.validators.dynamic_json_validator import (
    DynamicJSONValidator
)


validation_bp = Blueprint("validation", __name__)


@validation_bp.route("/analyze", methods=["POST"])
def analyze_json():

    payload = request.get_json(silent=True)

    if payload is None:
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    result = DynamicJSONValidator.analyze(payload)

    if not result["valid"]:
        return jsonify({
            "success": False,
            "message": "JSON validation failed",
            "errors": result["errors"]
        }), 400

    return jsonify({
        "success": True,
        "message": "JSON analyzed successfully",
        "data": result
    }), 200