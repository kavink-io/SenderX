
from flask import Blueprint, request, jsonify, current_app, g

from app.modules.dead_letters.service import DeadLetterService
from app.modules.auth.decorators import require_roles


dead_letters_bp = Blueprint("dead_letters", __name__)

READ_ROLES = ("SUPER_ADMIN", "ADMIN", "VIEWER")
MANAGE_ROLES = ("SUPER_ADMIN", "ADMIN")
SUPER_ADMIN_ONLY = ("SUPER_ADMIN",)


@dead_letters_bp.route("/", methods=["GET"])
@require_roles(*READ_ROLES)
def get_all_dead_letters():

    result = DeadLetterService.get_all_dead_letters(
        limit=request.args.get("limit", 50),
        page=request.args.get("page", 1),
        status=request.args.get("status"),
        message_id=request.args.get("message_id"),
        recipient=request.args.get("recipient"),
        provider=request.args.get("provider")
    )

    return jsonify(result), 200 if result["success"] else 400


@dead_letters_bp.route("/statistics", methods=["GET"])
@require_roles(*READ_ROLES)
def get_dead_letter_statistics():

    result = DeadLetterService.get_statistics()

    return jsonify(result), 200 if result["success"] else 500


@dead_letters_bp.route("/analytics/providers", methods=["GET"])
@require_roles(*READ_ROLES)
def get_provider_analytics():

    result = DeadLetterService.get_provider_analytics()

    return jsonify(result), 200 if result["success"] else 500


@dead_letters_bp.route("/analytics/trends", methods=["GET"])
@require_roles(*READ_ROLES)
def get_failure_trends():

    try:
        result = DeadLetterService.get_failure_trends(
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            provider=request.args.get("provider")
        )

        return jsonify(result), 200 if result.get("success") else 500

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


@dead_letters_bp.route("/<string:message_id>", methods=["GET"])
@require_roles(*READ_ROLES)
def get_dead_letter(message_id):

    result = DeadLetterService.get_dead_letter(message_id)

    return jsonify(result), 200 if result["success"] else 404


@dead_letters_bp.route("/<string:message_id>/history", methods=["GET"])
@require_roles(*READ_ROLES)
def get_retry_history(message_id):

    result = DeadLetterService.get_retry_history(message_id)

    if not result["success"]:
        status_code = (
            404 if result["message"] == "Dead letter not found"
            else 500
        )
        return jsonify(result), status_code

    return jsonify(result), 200


@dead_letters_bp.route("/<string:message_id>/retry", methods=["POST"])
@require_roles(*MANAGE_ROLES)
def retry_dead_letter(message_id):

    result = DeadLetterService.retry_dead_letter(message_id)

    if not result["success"]:
        status_code = (
            404 if result["message"] == "Dead letter not found"
            else 400
        )
        return jsonify(result), status_code

    return jsonify(result), 202


@dead_letters_bp.route("/<string:message_id>", methods=["DELETE"])
@require_roles(*MANAGE_ROLES)
def delete_dead_letter(message_id):

    payload = request.get_json(silent=True) or {}
    confirm = payload.get("confirm", False)

    result = DeadLetterService.delete_dead_letter(
        message_id,
        confirm=confirm
    )

    if not result["success"]:

        if result["message"] == "Dead letter not found":
            status_code = 404
        elif "status may have changed" in result["message"]:
            status_code = 409
        else:
            status_code = 400

        return jsonify(result), status_code

    return jsonify(result), 200


@dead_letters_bp.route("/recovery/stale-dispatches", methods=["POST"])
@require_roles(*SUPER_ADMIN_ONLY)
def recover_stale_dispatches():

    try:
        minutes = request.args.get("minutes", 5, type=int)
        limit = request.args.get("limit", 100, type=int)

        if minutes < 1:
            return jsonify({
                "success": False,
                "message": "Minutes must be at least 1"
            }), 400

        if not 1 <= limit <= 500:
            return jsonify({
                "success": False,
                "message": "Limit must be between 1 and 500"
            }), 400

        result = DeadLetterService.recover_stale_dispatches(
            minutes=minutes,
            limit=limit
        )

        return jsonify(result), 200 if result.get("success") else 500

    except Exception:
        current_app.logger.exception(
            "Stale dispatch recovery endpoint failed"
        )

        return jsonify({
            "success": False,
            "message": "Recovery operation failed"
        }), 500


@dead_letters_bp.route("/recovery/inspect", methods=["GET"])
@require_roles(*READ_ROLES)
def inspect_recovery_required():

    result = DeadLetterService.inspect_recovery_required()

    return jsonify(result), 200 if result.get("success") else 500


@dead_letters_bp.route("/recovery/tasks/<string:task_id>", methods=["GET"])
@require_roles(*READ_ROLES)
def inspect_celery_task(task_id):

    result = DeadLetterService.inspect_dispatch_task(task_id)

    return jsonify(result), 200 if result.get("success") else 500


@dead_letters_bp.route("/recovery/reconcile", methods=["GET"])
@require_roles(*SUPER_ADMIN_ONLY)
def reconcile_recovery_required():

    result = DeadLetterService.reconcile_recovery_required()

    return jsonify(result), 200 if result.get("success") else 500


@dead_letters_bp.route(
    "/recovery/<string:message_id>/resolve",
    methods=["POST"]
)
@require_roles(*MANAGE_ROLES)
def resolve_recovery(message_id):

    try:
        data = request.get_json(silent=True) or {}
        notes = data.get("notes")

        if notes is not None and not isinstance(notes, str):
            return jsonify({
                "success": False,
                "message": "notes must be a string"
            }), 400

        if notes is not None:
            notes = notes.strip()

        if notes and len(notes) > 1000:
            return jsonify({
                "success": False,
                "message": "notes must not exceed 1000 characters"
            }), 400

        admin = g.current_admin

        resolved_by = admin["email"]

        result = DeadLetterService.resolve_recovery(
            message_id=message_id,
            resolved_by=resolved_by,
            notes=notes
        )

        return jsonify(result), 200 if result.get("success") else 400

    except Exception:
        current_app.logger.exception(
            "Recovery resolution endpoint failed"
        )

        return jsonify({
            "success": False,
            "message": "Recovery resolution failed"
        }), 500
