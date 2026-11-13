
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
            "message": result.get("message", "Message validation failed"),
            "errors": result.get("errors", [result.get("message")] if result.get("message") else [])
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

    result = MessageService.get_all_messages(
        organization_id=organization_id,
        limit=request.args.get("limit", 50),
        page=request.args.get("page", 1),
        status=request.args.get("status"),
        channel=request.args.get("channel"),
        provider=request.args.get("provider"),
        recipient=request.args.get("recipient")
    )

    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"]
    }), 200


@messages_bp.route("/<string:message_id>/queue", methods=["POST"])
@require_permissions("organization:messages:manage")
def queue_message(message_id):

    organization_id = g.current_organization["organization_id"]

    result = MessageService.queue_message(
        message_id=message_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    response_body = {k: v for k, v in result.items() if k != "status_code"}

    return jsonify(response_body), status_code


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

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    response_body = {k: v for k, v in result.items() if k != "status_code"}

    return jsonify(response_body), status_code


@messages_bp.route("/webhook/twilio", methods=["POST"])
@messages_bp.route("/callbacks/twilio", methods=["POST"])
def twilio_status_callback():
    """
    Twilio StatusCallback webhook endpoint.
    Accepts application/x-www-form-urlencoded (Twilio default) or application/json.
    Does not require user JWT authentication as it is invoked by Twilio.
    """
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    result = MessageService.handle_twilio_callback(data)
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@messages_bp.route("/webhook/whatsapp", methods=["GET"])
def whatsapp_webhook_verification():
    """
    Meta WhatsApp Cloud API Webhook Handshake Verification.
    GET /api/v1/messages/webhook/whatsapp
    Meta query parameters:
      - hub.mode
      - hub.verify_token
      - hub.challenge
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    result = MessageService.verify_whatsapp_webhook(
        hub_mode=mode,
        hub_token=token,
        hub_challenge=challenge
    )
    if result.get("success"):
        # Meta requires returning the challenge string/int with status 200
        return str(result.get("challenge")), 200
    return jsonify(result), result.get("status_code", 403)


@messages_bp.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook_event():
    """
    Meta WhatsApp Cloud API Webhook Event Notifications.
    POST /api/v1/messages/webhook/whatsapp
    Verifies X-Hub-Signature-256 header and processes message status updates & inbound messages.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    raw_payload = request.get_data()
    payload = request.get_json(silent=True) or {}

    result = MessageService.handle_whatsapp_webhook(
        raw_payload=raw_payload,
        signature_header=signature,
        json_data=payload
    )
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


