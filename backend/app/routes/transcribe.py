import time
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..config import Settings
from ..services.transcription_service import TranscriptionService
from ..utils.files import delete_file_quietly, is_allowed_audio_file

transcribe_bp = Blueprint("transcribe", __name__)
service = TranscriptionService()


@transcribe_bp.post("/api/transcribe")
def transcribe_audio():
    started_at = time.perf_counter()
    settings: Settings = current_app.config["SETTINGS"]

    if "audio" not in request.files:
        return error_response("Missing multipart field: audio.", "MISSING_AUDIO", 400)

    audio = request.files["audio"]
    validation_error = validate_audio(audio)
    if validation_error:
        return validation_error

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(secure_filename(audio.filename or "recording.webm")).suffix.lower()
    temp_path = settings.upload_dir / f"{uuid4().hex}{suffix}"

    try:
        audio.save(temp_path)
        current_app.logger.info("Transcribing upload %s", temp_path.name)
        result = service.transcribe(temp_path, settings)
        processing_time = round(time.perf_counter() - started_at, 3)

        return jsonify(
            {
                "success": True,
                "text": result.text,
                "language": result.language,
                "detectedLanguage": result.detected_language,
                "languageFallbackUsed": result.language_fallback_used,
                "processingTime": processing_time,
                "duration": result.duration,
                "segments": [
                    {
                        "id": segment.id,
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                    }
                    for segment in result.segments
                ],
            }
        )
    except ValueError as error:
        current_app.logger.warning("Transcription validation failed: %s", error)
        return error_response(str(error), "TRANSCRIPTION_VALIDATION_FAILED", 400)
    except Exception as error:
        current_app.logger.exception("Transcription failed: %s", error)
        return error_response("Unable to transcribe audio.", "TRANSCRIPTION_FAILED", 500)
    finally:
        delete_file_quietly(temp_path)


def validate_audio(audio: FileStorage):
    if not audio.filename:
        return error_response("Audio filename is required.", "INVALID_FILENAME", 400)

    if not is_allowed_audio_file(audio.filename, audio.mimetype):
        return error_response("Unsupported audio file type.", "UNSUPPORTED_AUDIO", 415)

    return None


def error_response(message: str, code: str, status: int):
    return jsonify({"success": False, "error": message, "code": code}), status
