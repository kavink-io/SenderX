"""
SenderX Media Management Routes
Exposes organization-scoped REST endpoints for uploading, listing, downloading,
and deleting media attachments.
"""

from typing import List
from flask import Blueprint, request, jsonify, g, send_file, redirect, Response
from app.modules.auth.decorators import require_permissions, require_organization_wide_scope
from app.modules.media.service import MediaService

media_bp = Blueprint("media", __name__)


# ---------------------------------------------------------------------------
# 1. SINGLE FILE UPLOAD
# ---------------------------------------------------------------------------
@media_bp.route("/upload", methods=["POST"])
@require_permissions("organization:media:upload")
def upload_media():
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    """
    POST /api/v1/media/upload
    Form-data parameters:
    - file / media: binary file
    - purpose: optional string description
    - channel: optional target channel
    - expires_in_seconds / expires_in_days: optional retention
    """
    uploaded_file = request.files.get("file") or request.files.get("media")
    if not uploaded_file:
        return jsonify({
            "success": False,
            "message": "No file uploaded. Multipart form field 'file' is required."
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    purpose = request.form.get("purpose")
    channel = request.form.get("channel")

    expires_in_sec = request.form.get("expires_in_seconds", type=int)
    expires_in_days = request.form.get("expires_in_days", type=int)

    result = MediaService.upload_file(
        file_obj=uploaded_file,
        organization_id=organization_id,
        user_id=user_id,
        purpose=purpose,
        channel=channel,
        expires_in_seconds=expires_in_sec,
        expires_in_days=expires_in_days
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 2. BULK FILE UPLOAD
# ---------------------------------------------------------------------------
@media_bp.route("/bulk-upload", methods=["POST"])
@require_permissions("organization:media:upload")
def bulk_upload_media():
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    """
    POST /api/v1/media/bulk-upload
    Multipart form-data with multiple files under 'files' or 'file'.
    """
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        return jsonify({
            "success": False,
            "message": "No files uploaded. Multipart form field 'files' is required."
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    purpose = request.form.get("purpose")
    expires_in_sec = request.form.get("expires_in_seconds", type=int)
    expires_in_days = request.form.get("expires_in_days", type=int)

    result = MediaService.bulk_upload(
        files_list=files,
        organization_id=organization_id,
        user_id=user_id,
        purpose=purpose,
        expires_in_seconds=expires_in_sec,
        expires_in_days=expires_in_days
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 3. LIST MEDIA
# ---------------------------------------------------------------------------
@media_bp.route("/", methods=["GET"])
@media_bp.route("", methods=["GET"])
@require_permissions("organization:media:read")
def list_media():
    """
    GET /api/v1/media
    Query parameters:
    - page, limit, mime_type, status, channel, search
    """
    organization_id = g.current_organization["organization_id"]

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 50))))
    except (ValueError, TypeError):
        page = 1
        limit = 50

    mime_type = request.args.get("mime_type")
    status = request.args.get("status")
    channel = request.args.get("channel")
    search = request.args.get("search")

    result = MediaService.list_media(
        organization_id=organization_id,
        page=page,
        limit=limit,
        mime_type=mime_type,
        status=status,
        channel=channel,
        search=search
    )

    return jsonify({
        "success": True,
        "data": result["data"],
        "pagination": result["pagination"]
    }), 200


# ---------------------------------------------------------------------------
# 4. GET MEDIA METADATA
# ---------------------------------------------------------------------------
@media_bp.route("/<string:media_id>", methods=["GET"])
@require_permissions("organization:media:read")
def get_media(media_id: str):
    """
    GET /api/v1/media/<media_id>
    Retrieve metadata without downloading the binary payload.
    """
    organization_id = g.current_organization["organization_id"]

    result = MediaService.get_media(
        media_id=media_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 5. SECURE DOWNLOAD
# ---------------------------------------------------------------------------
@media_bp.route("/<string:media_id>/download", methods=["GET"])
@require_permissions("organization:media:read")
def download_media(media_id: str):
    """
    GET /api/v1/media/<media_id>/download
    Streams the binary file with security headers or redirects to a pre-signed URL.
    """
    organization_id = g.current_organization["organization_id"]
    prefer_signed = request.args.get("signed", "false").lower() == "true"

    result = MediaService.download_media(
        media_id=media_id,
        organization_id=organization_id,
        prefer_signed_url=prefer_signed
    )

    if not result.get("success"):
        return jsonify(result), result.get("status_code", 404)

    # Redirect mode (e.g. S3 pre-signed URL)
    if result.get("download_mode") == "redirect":
        return redirect(result["url"], code=302)

    # Streaming mode
    stream = result["stream"]
    filename = result.get("filename", "download")
    mime_type = result.get("mime_type", "application/octet-stream")

    resp = send_file(
        stream,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )
    # Security headers
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# ---------------------------------------------------------------------------
# 6. DELETE MEDIA
# ---------------------------------------------------------------------------
@media_bp.route("/<string:media_id>", methods=["DELETE"])
@require_permissions("organization:media:delete")
def delete_media(media_id: str):
    scope_err = require_organization_wide_scope()
    if scope_err:
        return scope_err
    """
    DELETE /api/v1/media/<media_id>
    Deletes the underlying storage file and marks metadata as DELETED.
    """
    organization_id = g.current_organization["organization_id"]

    result = MediaService.delete_media(
        media_id=media_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code
