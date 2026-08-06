"""
routes/files.py — File Management Routes

Endpoints:
    POST   /api/upload          → Upload a file (to S3 or local)
    GET    /api/files           → List all files for current user
    GET    /api/files/<int:id>  → Get metadata for a single file
    GET    /api/files/<int:id>/download → Download a file
    DELETE /api/files/<int:id>  → Delete a file

NOTE: Full implementation is in Phase 2.
      This stub allows app.py to start without import errors.
"""

import os
import uuid
import logging
from datetime import datetime

from flask import (
    Blueprint, request, jsonify, send_from_directory,
    current_app, redirect
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database.models import db, FileRecord, UploadLog

logger = logging.getLogger(__name__)

files_bp = Blueprint("files", __name__)


def _allowed_file(filename: str) -> bool:
    """Return True if the file extension is in the allowed set."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


def _log_action(user_id, file_id, action, success=True, error_msg=None, details=None):
    """Write an entry to the upload_logs audit table."""
    try:
        log = UploadLog(
            user_id    = user_id,
            file_id    = file_id,
            action     = action,
            success    = success,
            error_msg  = error_msg,
            details    = details,
            ip_address = request.remote_addr,
            user_agent = request.headers.get("User-Agent", "")[:255],
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")


# ─────────────────────────────────────────────────────────────────────
# POST /api/upload
# ─────────────────────────────────────────────────────────────────────
@files_bp.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    """
    Upload a file.

    Request: multipart/form-data with key "file"
    Response (201):
        { "message": "...", "file": { ... } }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename):
        return jsonify({
            "error": "File type not allowed",
            "allowed_types": list(current_app.config.get("ALLOWED_EXTENSIONS", []))
        }), 415

    # Sanitise filename to prevent directory traversal attacks
    original_name  = file.filename
    safe_name      = secure_filename(original_name)
    file_ext       = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    unique_name    = f"{uuid.uuid4().hex}_{safe_name}"

    requested_backend = request.form.get("storage_backend")
    if requested_backend and requested_backend not in {"local", "s3"}:
        return jsonify({"error": "Storage destination must be 'local' or 's3'"}), 400

    from services.s3_service import S3Service
    s3 = S3Service()
    if requested_backend == "s3" and not s3.is_configured():
        return jsonify({"error": "S3 storage is not configured"}), 503

    # Preserve the previous API behavior for clients that omit this field.
    use_s3 = requested_backend == "s3" if requested_backend else s3.is_configured()

    file_content = file.read()
    file_size    = len(file_content)
    content_type = file.content_type or "application/octet-stream"

    record = FileRecord(
        user_id           = current_user.id,
        original_filename = original_name,
        stored_filename   = unique_name,
        file_extension    = file_ext,
        file_size         = file_size,
        content_type      = content_type,
    )

    if use_s3:
        # ── Upload to S3 ──────────────────────────────────────────
        s3_key = f"uploads/user_{current_user.id}/{unique_name}"
        success, url, err = s3.upload_fileobj(
            fileobj      = file_content,
            s3_key       = s3_key,
            content_type = content_type,
        )
        if not success:
            _log_action(current_user.id, None, "upload", success=False, error_msg=err)
            return jsonify({"error": f"S3 upload failed: {err}"}), 500

        record.s3_key          = s3_key
        record.storage_backend = "s3"
        record.download_url    = url

    else:
        # ── Store locally ─────────────────────────────────────────
        upload_dir = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
        os.makedirs(upload_dir, exist_ok=True)
        local_path = os.path.join(upload_dir, unique_name)

        with open(local_path, "wb") as f:
            f.write(file_content)

        record.local_path      = local_path
        record.storage_backend = "local"

    try:
        db.session.add(record)
        db.session.commit()
        _log_action(current_user.id, record.id, "upload", success=True)
        logger.info(f"File uploaded: {original_name} by user {current_user.username}")
    except Exception as exc:
        db.session.rollback()
        logger.error(f"DB error saving file record: {exc}")
        return jsonify({"error": "Database error saving file record"}), 500

    return jsonify({
        "message": "File uploaded successfully",
        "file": record.to_dict()
    }), 201


# ─────────────────────────────────────────────────────────────────────
# GET /api/files
# ─────────────────────────────────────────────────────────────────────
@files_bp.route("/api/files", methods=["GET"])
@login_required
def list_files():
    """
    List all non-deleted files belonging to the current user.

    Query params:
        search=<str>   → filter by filename (partial match)
        limit=<int>    → max results (default 100)
        offset=<int>   → pagination offset (default 0)

    Response (200):
        {
            "files": [ {...}, ... ],
            "total": 42,
            "storage_used": 10485760
        }
    """
    search = request.args.get("search", "").strip()
    limit  = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    query = FileRecord.query.filter_by(
        user_id    = current_user.id,
        is_deleted = False
    )

    if search:
        query = query.filter(
            FileRecord.original_filename.ilike(f"%{search}%")
        )

    total = query.count()

    # Calculate total storage used (sum of file_size for non-deleted files)
    from sqlalchemy import func
    storage_result = db.session.query(
        func.sum(FileRecord.file_size)
    ).filter_by(user_id=current_user.id, is_deleted=False).scalar()
    storage_used = storage_result or 0

    files = (
        query
        .order_by(FileRecord.uploaded_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return jsonify({
        "files":        [f.to_dict() for f in files],
        "total":        total,
        "storage_used": storage_used,
        "limit":        limit,
        "offset":       offset,
    }), 200


# ─────────────────────────────────────────────────────────────────────
# GET /api/files/<id>
# ─────────────────────────────────────────────────────────────────────
@files_bp.route("/api/files/<int:file_id>", methods=["GET"])
@login_required
def get_file(file_id: int):
    """
    Get metadata for a single file.

    Response (200):  { "file": { ... } }
    """
    record = FileRecord.query.filter_by(
        id         = file_id,
        user_id    = current_user.id,
        is_deleted = False
    ).first_or_404(description="File not found or access denied")

    return jsonify({"file": record.to_dict()}), 200


# ─────────────────────────────────────────────────────────────────────
# GET /api/files/<id>/download
# ─────────────────────────────────────────────────────────────────────
@files_bp.route("/api/files/<int:file_id>/download", methods=["GET"])
@login_required
def download_file(file_id: int):
    """
    Download a file.

    - If stored in S3: redirects to a pre-signed URL (valid 60 minutes)
    - If stored locally: serves the file directly from /uploads
    """
    record = FileRecord.query.filter_by(
        id         = file_id,
        user_id    = current_user.id,
        is_deleted = False
    ).first_or_404(description="File not found or access denied")

    _log_action(current_user.id, record.id, "download")

    if record.storage_backend == "s3":
        try:
            from services.s3_service import S3Service
            s3  = S3Service()
            url = s3.generate_presigned_url(record.s3_key, expiry_seconds=3600)
            return redirect(url)
        except Exception as exc:
            logger.error(f"S3 presigned URL error: {exc}")
            return jsonify({"error": "Could not generate download link"}), 500

    # Local storage
    if not record.local_path or not os.path.exists(record.local_path):
        return jsonify({"error": "File not found on server"}), 404

    upload_dir = os.path.dirname(record.local_path)
    return send_from_directory(
        upload_dir,
        os.path.basename(record.local_path),
        as_attachment=True,
        download_name=record.original_filename,
    )


# ─────────────────────────────────────────────────────────────────────
# DELETE /api/files/<id>
# ─────────────────────────────────────────────────────────────────────
@files_bp.route("/api/files/<int:file_id>", methods=["DELETE"])
@login_required
def delete_file(file_id: int):
    """
    Soft-delete a file (marks is_deleted=True in DB, removes from storage).

    Response (200):  { "message": "File deleted" }
    """
    record = FileRecord.query.filter_by(
        id         = file_id,
        user_id    = current_user.id,
        is_deleted = False
    ).first_or_404(description="File not found or access denied")

    # Delete from S3
    if record.storage_backend == "s3" and record.s3_key:
        try:
            from services.s3_service import S3Service
            s3 = S3Service()
            s3.delete_object(record.s3_key)
        except Exception as exc:
            logger.warning(f"S3 delete failed for key {record.s3_key}: {exc}")

    # Delete from local storage
    if record.storage_backend == "local" and record.local_path:
        try:
            if os.path.exists(record.local_path):
                os.remove(record.local_path)
        except OSError as exc:
            logger.warning(f"Local file delete failed: {exc}")

    # Soft-delete in database
    record.is_deleted = True
    record.deleted_at = datetime.utcnow()

    try:
        db.session.commit()
        _log_action(current_user.id, record.id, "delete", success=True)
        logger.info(f"File deleted: id={file_id} by {current_user.username}")
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": "Database error during delete"}), 500

    return jsonify({"message": "File deleted successfully"}), 200
