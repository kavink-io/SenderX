from flask import Blueprint, jsonify, g

from app.modules.analytics.service import AnalyticsService
from app.modules.auth.decorators import require_roles, require_permissions

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/platform", methods=["GET"])
@require_roles("SUPER_ADMIN")
def get_platform_analytics():
    data = AnalyticsService.get_platform_analytics()
    return jsonify(data), 200


@analytics_bp.route("/organization", methods=["GET"])
@require_permissions("organization:analytics:read")
def get_organization_analytics():
    organization_id = g.current_organization["organization_id"]
    data = AnalyticsService.get_organization_analytics(organization_id=organization_id)
    return jsonify(data), 200
