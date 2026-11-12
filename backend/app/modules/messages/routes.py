
from flask import Blueprint, request, jsonify, g

from app.modules.messages.service import MessageService
from app.modules.auth.decorators import require_permissions


messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/", methods=["POST"])
@require_permissions("organization:messages:create")
def create_message():

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]

    result = MessageService.create_message(
        payload,
        organization_id
    )

    if not result["success"]:
        return jsonify({
            "success": False,
            "message": "Message validation failed",
            "errors": result.get("errors", [])
        }), 400

    return jsonify({
        "success": True,
        "message": "Message created and stored successfully",
        "data": result
    }), 201


@messages_bp.route("/<string:message_id>", methods=["GET"])
@require_permissions("organization:messages:read")
def get_message(message_id):

    organization_id = g.current_organization["organization_id"]

    message = MessageService.get_message(
        message_id,
        organization_id
    )

    if not message:
        return jsonify({
            "success": False,
            "message": "Message not found"
        }), 404

    return jsonify({
        "success": True,
        "data": message
    }), 200


@messages_bp.route("/", methods=["GET"])
@require_permissions("organization:messages:read")
def get_all_messages():

    organization_id = g.current_organization["organization_id"]

    messages = MessageService.get_all_messages(
        organization_id
    )

    return jsonify({
        "success": True,
        "count": len(messages),
        "data": messages
    }), 200


@messages_bp.route("/<string:message_id>/status", methods=["PATCH"])
@require_permissions("organization:messages:manage")
def update_message_status(message_id):

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    if not isinstance(new_status, str) or not new_status:
        return jsonify({
            "success": False,
            "message": "Status is required"
        }), 400

    organization_id = g.current_organization["organization_id"]

    result = MessageService.update_status(
        message_id,
        new_status,
        organization_id
    )

    if not result["success"]:
        status_code = (
            404 if result["message"] == "Message not found"
            else 400
        )

        return jsonify(result), status_code

    return jsonify(result), 200
