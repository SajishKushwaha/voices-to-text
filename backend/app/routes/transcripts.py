from flask import Blueprint, current_app, jsonify, request

from ..config import Settings
from ..database import get_connection, insert_audit_log, row_to_dict, utc_now

transcripts_bp = Blueprint("transcripts", __name__)


@transcripts_bp.post("/api/transcripts")
def save_transcript():
    settings: Settings = current_app.config["SETTINGS"]
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    language = str(payload.get("language") or "")
    source = str(payload.get("source") or "voice_to_text")
    duration_seconds = payload.get("durationSeconds")

    if not text:
        return error_response("Transcript text is required.", "EMPTY_TRANSCRIPT", 400)

    now = utc_now()
    with get_connection(settings.database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO transcripts (text, language, duration_seconds, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (text, language, duration_seconds, source, now),
        )
        transcript_id = int(cursor.lastrowid)
        insert_audit_log(
            connection,
            entity_type="transcript",
            entity_id=transcript_id,
            action="save",
            metadata={"language": language, "source": source},
        )

    return jsonify({"success": True, "id": transcript_id, "createdAt": now})


@transcripts_bp.get("/api/transcripts")
def list_transcripts():
    settings: Settings = current_app.config["SETTINGS"]
    with get_connection(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, text, language, duration_seconds, source, created_at
            FROM transcripts
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).fetchall()

    return jsonify({"success": True, "transcripts": [row_to_dict(row) for row in rows]})


def error_response(message: str, code: str, status: int):
    return jsonify({"success": False, "error": message, "code": code}), status
