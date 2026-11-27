
from flask import Blueprint, request, jsonify, g

from app.modules.messages.service import MessageService
from app.modules.auth.decorators import require_permissions, resolve_authorized_application_scope
from app.modules.api_credentials.decorators import require_api_key_or_token


messages_bp = Blueprint("messages", __name__)


@messages_bp.route("", methods=["POST"])
@messages_bp.route("/", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:messages:create"])
def create_message():

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    # Reject any client attempt to enable or influence platform provider fallback
    data_block = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    forbidden_fallback_keys = ("use_platform_provider", "allow_platform_fallback")
    if (
        any(k in payload for k in forbidden_fallback_keys)
        or any(k in data_block for k in forbidden_fallback_keys)
        or any(k in request.args for k in forbidden_fallback_keys)
        or request.headers.get("X-Use-Platform-Provider") is not None
        or request.headers.get("X-Allow-Platform-Fallback") is not None
    ):
        return jsonify({
            "success": False,
            "message": "Platform-level provider fallback cannot be requested by clients"
        }), 403

    # External credentials must state an explicit channel; silently routing to
    # the service's legacy email default can send to the wrong provider.
    if getattr(g, "auth_type", None) == "API_KEY" and not (
        isinstance(payload.get("channel"), str) and payload.get("channel").strip()
    ):
        return jsonify({
            "success": False,
            "message": "channel is required for API credential requests",
            "errors": ["Provide an explicit channel such as whatsapp, email, or sms"],
        }), 422

    organization_id = g.current_organization["organization_id"]

    if getattr(g, "auth_type", None) != "API_KEY":
        from flask import current_app
        from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError

        current_user = getattr(g, "current_user", None) or {}
        user_id = current_user.get("user_id") or "anonymous"
        try:
            u_ok, u_retry = DistributedRateLimiter.check_rate_limit(
                "message_create_user",
                DistributedRateLimiter.hash_identifier("msg_user", f"{organization_id}:{user_id}"),
                limit=int(current_app.config.get("RATE_LIMIT_MESSAGE_CREATE_USER_RPM", 120)),
                window_seconds=60,
            )
            if not u_ok:
                resp = jsonify({"success": False, "message": "Rate limit exceeded for message creation.", "retry_after": u_retry})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(u_retry)
                return resp
            o_ok, o_retry = DistributedRateLimiter.check_rate_limit(
                "message_create_org",
                str(organization_id),
                limit=int(current_app.config.get("RATE_LIMIT_MESSAGE_CREATE_ORG_RPM", 1000)),
                window_seconds=60,
            )
            if not o_ok:
                resp = jsonify({"success": False, "message": "Organization message rate limit exceeded.", "retry_after": o_retry})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(o_retry)
                return resp
        except RateLimiterError:
            return jsonify({
                "success": False,
                "message": "Rate limiting service temporarily unavailable. Please retry later."
            }), 503

    # Resolve application_id and enforce employee / API-key application scoping
    user_app_scopes = resolve_authorized_application_scope()
    raw_body_app = payload.get("application_id")
    if raw_body_app is not None and not isinstance(raw_body_app, str):
        return jsonify({"success": False, "message": "application_id must be a string"}), 400

    app_id = (
        (raw_body_app.strip() if isinstance(raw_body_app, str) and raw_body_app.strip() else None)
        or (request.headers.get("X-Application-ID") or "").strip()
        or getattr(g, "current_application_id", None)
    )
    credential_app_id = getattr(g, "current_application_id", None) if getattr(g, "auth_type", None) == "API_KEY" else None
    if credential_app_id and app_id and str(app_id).strip() != str(credential_app_id).strip():
        return jsonify({"success": False, "message": "Application ID does not match the API credential"}), 403
    if credential_app_id:
        app_id = str(credential_app_id).strip()

    if user_app_scopes is not None:
        if not app_id:
            if len(user_app_scopes) == 1:
                app_id = list(user_app_scopes)[0]
                payload["application_id"] = app_id
            else:
                return jsonify({
                    "success": False,
                    "message": "application_id is required within your authorized application scope"
                }), 400
        elif str(app_id).strip() not in user_app_scopes:
            return jsonify({
                "success": False,
                "message": f"You do not have permission to send messages for application '{app_id}'"
            }), 403

    result = MessageService.create_message(
        payload,
        organization_id,
        application_id=app_id
    )

    if not result["success"]:
        status_code = result.get("status_code", 400)
        return jsonify({
            "success": False,
            "message": result.get("message", "Message validation failed"),
            "errors": result.get("errors", [result.get("message")] if result.get("message") else [])
        }), status_code

    return jsonify({
        "success": True,
        "message": "Message created and stored successfully",
        "data": result
    }), 201


@messages_bp.route("/<string:message_id>", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:messages:read"])
def get_message(message_id):

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    is_api_key = getattr(g, "auth_type", None) == "API_KEY"

    message = MessageService.get_message(
        message_id,
        organization_id,
        user_application_ids=user_app_scopes,
        forbid_cross_app=not is_api_key,
    )

    if not message:
        return jsonify({
            "success": False,
            "message": "Message not found"
        }), 404

    if isinstance(message, dict) and message.get("_error") == "FORBIDDEN":
        return jsonify({
            "success": False,
            "message": message.get("message", "Access denied for this application scope")
        }), 403

    return jsonify({
        "success": True,
        "data": message
    }), 200


@messages_bp.route("", methods=["GET"])
@messages_bp.route("/", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:messages:read"])
def get_all_messages():

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)
    status = request.args.get("status", "").strip().upper() or None
    channel = request.args.get("channel", "").strip().lower() or None
    provider = request.args.get("provider", "").strip().lower() or None
    recipient = request.args.get("recipient", "").strip() or None
    application_id = request.args.get("application_id", "").strip() or getattr(g, "current_application_id", None)
    search = request.args.get("search", "").strip() or None
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None

    result = MessageService.get_all_messages(
        organization_id=organization_id,
        limit=limit,
        page=page,
        status=status,
        channel=channel,
        provider=provider,
        recipient=recipient,
        application_id=application_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        user_application_ids=user_app_scopes
    )

    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"]
    }), 200


@messages_bp.route("/<string:message_id>/retry", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:messages:manage"])
def retry_message(message_id):

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = MessageService.retry_message(
        message_id=message_id,
        organization_id=organization_id,
        user_application_ids=user_app_scopes
    )

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@messages_bp.route("/<string:message_id>/queue", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:messages:manage"])
def queue_message(message_id):

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = MessageService.queue_message(
        message_id=message_id,
        organization_id=organization_id,
        user_application_ids=user_app_scopes,
    )

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    response_body = {k: v for k, v in result.items() if k != "status_code"}

    return jsonify(response_body), status_code


@messages_bp.route("/<string:message_id>/status", methods=["PATCH"])
@require_api_key_or_token(required_permissions=["organization:messages:manage"])
def update_message_status(message_id):

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    if not isinstance(new_status, str) or not new_status:
        return jsonify({
            "success": False,
            "message": "Status is required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = MessageService.update_status(
        message_id,
        new_status,
        organization_id,
        user_application_ids=user_app_scopes,
    )

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    response_body = {k: v for k, v in result.items() if k != "status_code"}

    return jsonify(response_body), status_code


def _dispatch_twilio_callback_request(endpoint_kind):
    """
    Shared fail-closed request extractor for Twilio webhook / StatusCallback endpoints.
    Passes exact externally visible URL, signature header, and unflattened params for validation.
    """
    from app.modules.messages.twilio_webhook import reconstruct_twilio_callback_url

    signature = request.headers.get("X-Twilio-Signature")
    callback_url = reconstruct_twilio_callback_url(request)
    is_json = bool(request.is_json)
    has_body_sha256 = "bodySHA256" in request.args

    if is_json:
        raw_body = request.get_data(as_text=True) or ""
        callback_data = request.get_json(silent=True)
        validation_params = raw_body
    else:
        callback_data = request.form.to_dict(flat=True)
        validation_params = request.form

    result = MessageService.handle_twilio_callback(
        callback_data,
        signature=signature,
        callback_url=callback_url,
        validation_params=validation_params,
        endpoint_path=request.path,
        endpoint_kind=endpoint_kind,
        is_json=is_json,
        has_body_sha256=has_body_sha256,
    )
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@messages_bp.route("/webhook/twilio", methods=["POST"])
def twilio_webhook():
    """
    Twilio Webhook endpoint (status callbacks and authenticated webhook events).
    Validates X-Twilio-Signature using the receiving integration's encrypted Auth Token.
    """
    return _dispatch_twilio_callback_request(endpoint_kind="webhook")


@messages_bp.route("/callbacks/twilio", methods=["POST"])
def twilio_status_callback():
    """
    Dedicated Twilio StatusCallback delivery receipt endpoint.
    Requires signed delivery status parameters and updates only the verified tenant message.
    """
    return _dispatch_twilio_callback_request(endpoint_kind="status_callback")


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
    payload = request.get_json(silent=True)

    result = MessageService.handle_whatsapp_webhook(
        raw_payload=raw_payload,
        signature_header=signature,
        json_data=payload
    )
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


