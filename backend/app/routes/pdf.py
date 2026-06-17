import json
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..config import Settings
from ..database import get_connection, insert_audit_log, json_dumps, row_to_dict, utc_now
from ..services.pdf_extraction_service import PdfExtractionService

pdf_bp = Blueprint("pdf", __name__)
service = PdfExtractionService()


@pdf_bp.post("/api/pdf/extract")
def extract_pdf():
    settings: Settings = current_app.config["SETTINGS"]

    if "pdf" not in request.files:
        return error_response("Missing multipart field: pdf.", "MISSING_PDF", 400)

    upload = request.files["pdf"]
    validation_error = validate_pdf(upload)
    if validation_error:
        return validation_error

    settings.pdf_upload_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(upload.filename or "lab-report.pdf")
    stored_path = settings.pdf_upload_dir / f"{uuid4().hex}-{filename}"
    upload.save(stored_path)

    result = service.extract(stored_path)
    now = utc_now()

    with get_connection(settings.database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO pdf_reports (
              original_filename, stored_path, extracted_text, extracted_data,
              confidence, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                str(stored_path),
                result.extracted_text,
                json_dumps(result.data),
                result.confidence,
                "extracted",
                now,
                now,
            ),
        )
        report_id = int(cursor.lastrowid)
        insert_audit_log(
            connection,
            entity_type="pdf_report",
            entity_id=report_id,
            action="extract",
            metadata={
                "filename": filename,
                "confidence": result.confidence,
                "usedOcr": result.used_ocr,
                "warnings": result.warnings,
            },
        )

    return jsonify(
        {
            "success": True,
            "reportId": report_id,
            "filename": filename,
            "confidence": result.confidence,
            "usedOcr": result.used_ocr,
            "warnings": result.warnings,
            "data": result.data,
            "extractedText": result.extracted_text,
            "createdAt": now,
        }
    )


@pdf_bp.get("/api/pdf/reports")
def list_reports():
    settings: Settings = current_app.config["SETTINGS"]
    with get_connection(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, original_filename, confidence, status, created_at, updated_at
            FROM pdf_reports
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).fetchall()
    return jsonify({"success": True, "reports": [row_to_dict(row) for row in rows]})


@pdf_bp.get("/api/pdf/reports/<int:report_id>")
def get_report(report_id: int):
    settings: Settings = current_app.config["SETTINGS"]
    with get_connection(settings.database_path) as connection:
        row = connection.execute(
            "SELECT * FROM pdf_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        history = connection.execute(
            """
            SELECT id, reviewer, notes, reviewed_data, created_at
            FROM review_history
            WHERE report_id = ?
            ORDER BY created_at DESC
            """,
            (report_id,),
        ).fetchall()

    if row is None:
        return error_response("Report not found.", "REPORT_NOT_FOUND", 404)

    report = row_to_dict(row)
    report["extracted_data"] = json.loads(report["extracted_data"])
    return jsonify(
        {
            "success": True,
            "report": report,
            "reviewHistory": [row_to_dict(item) for item in history],
        }
    )


@pdf_bp.post("/api/pdf/reports/<int:report_id>/review")
def save_review(report_id: int):
    settings: Settings = current_app.config["SETTINGS"]
    payload = request.get_json(silent=True) or {}
    reviewed_data = payload.get("data")
    reviewer = str(payload.get("reviewer") or "Doctor")
    notes = str(payload.get("notes") or "")

    if not isinstance(reviewed_data, dict):
        return error_response("Reviewed data must be an object.", "INVALID_REVIEW_DATA", 400)

    now = utc_now()
    with get_connection(settings.database_path) as connection:
        row = connection.execute(
            "SELECT id FROM pdf_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if row is None:
            return error_response("Report not found.", "REPORT_NOT_FOUND", 404)

        connection.execute(
            """
            UPDATE pdf_reports
            SET extracted_data = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (json_dumps(reviewed_data), "reviewed", now, report_id),
        )
        connection.execute(
            """
            INSERT INTO review_history (report_id, reviewed_data, reviewer, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, json_dumps(reviewed_data), reviewer, notes, now),
        )
        insert_audit_log(
            connection,
            entity_type="pdf_report",
            entity_id=report_id,
            action="review_save",
            metadata={"reviewer": reviewer},
        )

    return jsonify({"success": True, "reportId": report_id, "savedAt": now})


def validate_pdf(upload: FileStorage):
    if not upload.filename:
        return error_response("PDF filename is required.", "INVALID_FILENAME", 400)

    suffix = Path(upload.filename).suffix.lower()
    mimetype = upload.mimetype or ""
    if suffix != ".pdf" or mimetype not in {"application/pdf", "application/octet-stream"}:
        return error_response("Only PDF files are supported.", "UNSUPPORTED_PDF", 415)

    return None


def error_response(message: str, code: str, status: int):
    return jsonify({"success": False, "error": message, "code": code}), status
