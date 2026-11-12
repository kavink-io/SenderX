from flask import Blueprint, request, jsonify

from app.modules.messages.service import MessageService

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/", methods=["POST"])
def create_message():

    payload = request.get_json(silent=True)

    if payload is None:
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    result = MessageService.create_message(payload)

    if not result["success"]:
        return jsonify({
            "success": False,
            "message": "Message validation failed",
            "errors": result["errors"]
        }), 400

    return jsonify({
        "success": True,
        "message": "Message created and stored successfully",
        "data": result
    }), 201


@messages_bp.route("/<string:message_id>", methods=["GET"])
def get_message(message_id):

    message = MessageService.get_message(message_id)

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
def get_all_messages():

    messages = MessageService.get_all_messages()

    return jsonify({
        "success": True,
        "count": len(messages),
        "data": messages
    }), 200

@messages_bp.route("/<string:message_id>/status", methods=["PATCH"])
def update_message_status(message_id):

    data = request.get_json(silent=True) or {}

    new_status = data.get("status")

    if not new_status:
        return jsonify({
            "success": False,
            "message": "Status is required"
        }), 400

    result = MessageService.update_status(
        message_id,
        new_status
    )

    if not result["success"]:
        status_code = (
            404 if result["message"] == "Message not found"
            else 400
        )

        return jsonify(result), status_code

    return jsonify(result), 200

