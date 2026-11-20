"""
SenderX Email Template Management Routes & Studio API

================================================================================
POWERSHELL / CURL USAGE GUIDE (Phase 5 Task 5.6: Email Template Studio)
================================================================================

1. Run the Backend:
   powershell.exe -ExecutionPolicy Bypass
   & "backend\\venv\\Scripts\\python.exe" backend\\run.py

2. Obtain an Authentication Token (Org Admin or Employee):
   $LOGIN_BODY = @{ email = "admin@example.com"; password = "YourSecurePassword123!" } | ConvertTo-Json
   $AUTH = Invoke-RestMethod -Method Post -Uri "http://localhost:5000/api/v1/auth/login" -ContentType "application/json" -Body $LOGIN_BODY
   $TOKEN = $AUTH.data.access_token

   Using curl.exe:
   curl.exe -s -X POST http://localhost:5000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"YourSecurePassword123!\"}"

3. Validate Template Syntax & Security (Pre-save check):
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/validate `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"name\":\"Welcome Email\",\"subject\":\"Welcome {{ user_name }}\",\"html_body\":\"<table><tr><td>Welcome {{ user_name }}</td></tr></table>\",\"variables\":[{\"name\":\"user_name\",\"type\":\"text\",\"required\":true}]}"

4. Create an Email Template:
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"name\":\"Welcome Email\",\"subject\":\"Welcome to SenderX, {{ recipient_name }}!\",\"html_body\":\"<table width='100%'><tr><td>Hello {{ recipient_name }}, welcome to our platform!</td></tr></table>\",\"css\":\".cta{color:#2563eb;}\",\"variables\":[{\"name\":\"recipient_name\",\"type\":\"text\",\"required\":true,\"sample_value\":\"Jane Doe\"}]}"

5. Live Preview (Draft or Standalone):
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/preview `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"subject\":\"Welcome {{ recipient_name }}\",\"html_body\":\"<table><tr><td>Welcome {{ recipient_name }}!</td></tr></table>\",\"sample_data\":{\"recipient_name\":\"Alex Taylor\"}}"

6. Publish Template:
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/tmpl-xyz123/publish `
     -H "Authorization: Bearer $TOKEN"

7. Send a Message Using the Template:
   curl.exe -s -X POST http://localhost:5000/api/v1/messages/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"channel\":\"email\",\"recipient\":\"user@example.com\",\"template_id\":\"tmpl-xyz123\",\"template_variables\":{\"recipient_name\":\"Jane Doe\"}}"

================================================================================
NEGATIVE SECURITY TESTS (EXPECTED REJECTIONS)
================================================================================

A. Script Tag Rejected (HTTP 422):
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"name\":\"Malicious 1\",\"subject\":\"Hi\",\"html_body\":\"<script>alert(1)</script>Hello\"}"

B. Javascript: URL Protocol Rejected (HTTP 422):
   curl.exe -s -X POST http://localhost:5000/api/v1/email-templates/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"name\":\"Malicious 2\",\"subject\":\"Hi\",\"html_body\":\"<a href='javascript:alert(1)'>Click here</a>\"}"

C. Header Injection (CR/LF in Subject) Rejected (HTTP 422):
   curl.exe -s -X POST http://localhost:5000/api/v1/messages/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"channel\":\"email\",\"recipient\":\"user@example.com\",\"template_id\":\"tmpl-xyz123\",\"template_variables\":{\"recipient_name\":\"Jane\\r\\nBcc: evil@attacker.com\"}}"

D. Unknown Key in Strict Mode Rejected (HTTP 422):
   curl.exe -s -X POST http://localhost:5000/api/v1/messages/ `
     -H "Authorization: Bearer $TOKEN" `
     -H "Content-Type: application/json" `
     -d "{\"channel\":\"email\",\"recipient\":\"user@example.com\",\"template_id\":\"tmpl-strict-id\",\"template_variables\":{\"recipient_name\":\"Jane\",\"unknown_key\":\"bad_data\"}}"
================================================================================
"""

from flask import Blueprint, request, jsonify, g, current_app
from app.modules.auth.decorators import require_permissions
from app.modules.api_credentials.rate_limiter import (
    DistributedRateLimiter,
    RateLimiterError
)
from app.modules.templates.service import TemplateService

templates_bp = Blueprint("templates", __name__)


# ---------------------------------------------------------------------------
# 1. CREATE TEMPLATE (POST / & POST /email-templates)
# ---------------------------------------------------------------------------
@templates_bp.route("", methods=["POST"])
@templates_bp.route("/", methods=["POST"])
@require_permissions("organization:templates:manage")
def create_template():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.create_template(
        data=payload,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 2. VALIDATE TEMPLATE (POST /validate)
# ---------------------------------------------------------------------------
@templates_bp.route("/validate", methods=["POST"])
@require_permissions("organization:templates:read")
def validate_template():
    user_id = g.current_user.get("user_id") or g.current_user.get("email") or "anonymous"
    try:
        is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
            dimension="template_validate",
            identifier=str(user_id),
            limit=current_app.config.get("RATE_LIMIT_TEMPLATE_VALIDATE_RPM", 60),
            window_seconds=60,
            fail_closed=True
        )
    except RateLimiterError:
        current_app.logger.error("Rate limiter service unavailable for template validate")
        return jsonify({
            "success": False,
            "message": "Rate limiting service temporarily unavailable. Please retry later."
        }), 503

    if not is_allowed:
        resp = jsonify({
            "success": False,
            "message": f"Rate limit exceeded for template operations. Please wait {retry_after} seconds before retrying.",
            "retry_after": retry_after
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]

    result = TemplateService.validate_template(
        data=payload,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 3. LIVE PREVIEW (POST /preview - Draft or By ID)
# ---------------------------------------------------------------------------
@templates_bp.route("/preview", methods=["POST"])
@require_permissions("organization:templates:read")
def preview_template_general():
    user_id = g.current_user.get("user_id") or g.current_user.get("email") or "anonymous"
    try:
        is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
            dimension="template_preview",
            identifier=str(user_id),
            limit=current_app.config.get("RATE_LIMIT_TEMPLATE_PREVIEW_RPM", 60),
            window_seconds=60,
            fail_closed=True
        )
    except RateLimiterError:
        current_app.logger.error("Rate limiter service unavailable for template preview")
        return jsonify({
            "success": False,
            "message": "Rate limiting service temporarily unavailable. Please retry later."
        }), 503

    if not is_allowed:
        resp = jsonify({
            "success": False,
            "message": f"Rate limit exceeded for template operations. Please wait {retry_after} seconds before retrying.",
            "retry_after": retry_after
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    payload = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]

    template_id = payload.get("template_id")
    sample_data = payload.get("sample_data") or {}
    html_body = payload.get("html_body") or payload.get("html")
    css = payload.get("css")
    subject = payload.get("subject")
    variables = payload.get("variables")

    result = TemplateService.preview_template(
        template_id=template_id,
        sample_data=sample_data,
        organization_id=organization_id,
        html_body=html_body,
        css=css,
        subject=subject,
        variables=variables
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


@templates_bp.route("/<string:template_id>/preview", methods=["GET", "POST"])
@require_permissions("organization:templates:read")
def preview_template_by_id(template_id):
    user_id = g.current_user.get("user_id") or g.current_user.get("email") or "anonymous"
    try:
        is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
            dimension="template_preview",
            identifier=str(user_id),
            limit=current_app.config.get("RATE_LIMIT_TEMPLATE_PREVIEW_RPM", 60),
            window_seconds=60,
            fail_closed=True
        )
    except RateLimiterError:
        current_app.logger.error("Rate limiter service unavailable for template preview by id")
        return jsonify({
            "success": False,
            "message": "Rate limiting service temporarily unavailable. Please retry later."
        }), 503

    if not is_allowed:
        resp = jsonify({
            "success": False,
            "message": f"Rate limit exceeded for template operations. Please wait {retry_after} seconds before retrying.",
            "retry_after": retry_after
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    payload = request.get_json(silent=True) or {}
    sample_data = payload.get("sample_data", payload) if isinstance(payload, dict) else {}
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.preview_template(
        template_id=template_id,
        sample_data=sample_data,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 4. STARTER LAYOUT (GET /starter-layout)
# ---------------------------------------------------------------------------
@templates_bp.route("/starter-layout", methods=["GET"])
@require_permissions("organization:templates:read")
def get_starter_layout():
    layout = TemplateService.get_starter_layout()
    return jsonify({"success": True, "data": layout}), 200


# ---------------------------------------------------------------------------
# 5. LIST TEMPLATES (GET /)
# ---------------------------------------------------------------------------
@templates_bp.route("", methods=["GET"])
@templates_bp.route("/", methods=["GET"])
@require_permissions("organization:templates:read")
def list_templates():
    organization_id = g.current_organization["organization_id"]

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 50))))
    except (ValueError, TypeError):
        page = 1
        limit = 50

    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")

    result = TemplateService.list_templates(
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status,
        category=category,
        search=search
    )

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# 6. GET TEMPLATE BY ID (GET /<id>)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template(template_id):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_template(
        template_id=template_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 7. UPDATE TEMPLATE (PUT & PATCH /<id>)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["PUT", "PATCH"])
@require_permissions("organization:templates:manage")
def update_template(template_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.update_template(
        template_id=template_id,
        data=payload,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 8. DELETE TEMPLATE (DELETE /<id>)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["DELETE"])
@require_permissions("organization:templates:manage")
def delete_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.delete_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 9. PUBLISH TEMPLATE (POST /<id>/publish)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/publish", methods=["POST"])
@require_permissions("organization:templates:manage")
def publish_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.publish_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 10. ARCHIVE TEMPLATE (POST /<id>/archive)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/archive", methods=["POST"])
@require_permissions("organization:templates:manage")
def archive_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.archive_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 11. DUPLICATE TEMPLATE (POST /<id>/duplicate)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/duplicate", methods=["POST"])
@require_permissions("organization:templates:manage")
def duplicate_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.duplicate_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 12. LIST TEMPLATE VERSIONS (GET /<id>/versions)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/versions", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template_versions(template_id):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_versions(
        template_id=template_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 13. GET SPECIFIC TEMPLATE VERSION (GET /<id>/versions/<v>)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/versions/<int:version>", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template_version(template_id, version):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_version(
        template_id=template_id,
        version=version,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code
