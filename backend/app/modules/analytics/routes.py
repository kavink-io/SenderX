from flask import Blueprint, jsonify, g, request

from app.modules.analytics.service import AnalyticsService
from app.modules.api_credentials.decorators import require_api_key_or_token
from app.modules.auth.decorators import require_roles, resolve_authorized_application_scope

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/platform", methods=["GET"])
@require_roles("SUPER_ADMIN")
def get_platform_analytics():
    data = AnalyticsService.get_platform_analytics()
    return jsonify(data), 200


@analytics_bp.route("/organization", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:analytics:read"])
def get_organization_analytics():
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    try:
        data = AnalyticsService.get_organization_analytics(
            organization_id=organization_id,
            start_date=request.args.get("start_date") or None,
            end_date=request.args.get("end_date") or None,
            application_id=getattr(g, "current_application_id", None),
            application_ids=user_app_scopes,
            include_details=request.args.get("include_details", "").lower() == "true"
        )
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    return jsonify(data), 200
