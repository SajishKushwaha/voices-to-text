import json
import logging
from threading import Lock, Semaphore

from flask import Blueprint, current_app, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from ..config import Settings
from ..services.streaming_transcription import (
    StreamValidationError,
    StreamingTranscriptionSession,
    parse_start_message,
)
from ..services.transcription_service import TranscriptionService

LOGGER = logging.getLogger(__name__)

stream_bp = Blueprint("stream", __name__)
sock = Sock()
service = TranscriptionService()
metrics_lock = Lock()
active_connections = 0
total_connections = 0
total_errors = 0
model_semaphore: Semaphore | None = None


@stream_bp.get("/api/metrics")
def stream_metrics():
    with metrics_lock:
        return {
            "activeWebSocketConnections": active_connections,
            "totalWebSocketConnections": total_connections,
            "totalWebSocketErrors": total_errors,
        }


@sock.route("/api/transcribe/stream")
def transcribe_stream(ws):
    settings: Settings = current_app.config["SETTINGS"]
    origin = request.headers.get("Origin")

    if not _origin_allowed(origin, settings):
        _safe_send(
            ws,
            {
                "type": "error",
                "code": "ORIGIN_NOT_ALLOWED",
                "error": "WebSocket origin is not allowed.",
            },
        )
        return

    _increment_connection()
    session = StreamingTranscriptionSession(
        ws=ws,
        settings=settings,
        service=service,
        model_semaphore=_get_model_semaphore(settings),
    )

    try:
        raw_start_message = ws.receive()
        if not isinstance(raw_start_message, str):
            raise StreamValidationError("First message must be JSON.", "INVALID_START")

        session.start(parse_start_message(raw_start_message))
        LOGGER.info("WebSocket transcription session started: %s", session.session_id)

        while True:
            message = ws.receive()
            if message is None:
                break

            if isinstance(message, bytes):
                session.accept_chunk(message)
                continue

            control = _parse_control_message(message)
            if control.get("type") == "stop":
                session.finish()
                break

            if control.get("type") == "ping":
                session.send({"type": "pong", "sessionId": session.session_id})
                continue

            raise StreamValidationError("Unknown control message.", "UNKNOWN_CONTROL")
    except ConnectionClosed:
        LOGGER.info("WebSocket transcription session closed: %s", session.session_id)
    except StreamValidationError as error:
        LOGGER.warning("WebSocket validation failed: %s", error)
        _increment_error()
        _safe_send(
            ws,
            {
                "type": "error",
                "sessionId": session.session_id,
                "code": error.code,
                "error": str(error),
            },
        )
    except Exception as error:
        LOGGER.exception("WebSocket transcription failed: %s", error)
        _increment_error()
        _safe_send(
            ws,
            {
                "type": "error",
                "sessionId": session.session_id,
                "code": "STREAM_FAILED",
                "error": "Unable to stream transcription.",
            },
        )
    finally:
        session.cleanup()
        _decrement_connection()


def init_stream_socket(app):
    sock.init_app(app)


def _parse_control_message(raw_message: str) -> dict:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as error:
        raise StreamValidationError("Invalid JSON control message.", "INVALID_JSON") from error

    if not isinstance(payload, dict):
        raise StreamValidationError("Control message must be an object.", "INVALID_CONTROL")

    return payload


def _origin_allowed(origin: str | None, settings: Settings) -> bool:
    if not origin:
        return True
    return origin in settings.cors_origins


def _safe_send(ws, payload: dict) -> None:
    try:
        ws.send(json.dumps(payload))
    except Exception:
        LOGGER.debug("Unable to send WebSocket payload.", exc_info=True)


def _get_model_semaphore(settings: Settings) -> Semaphore:
    global model_semaphore
    if model_semaphore is None:
        model_semaphore = Semaphore(max(1, settings.whisper_max_workers))
    return model_semaphore


def _increment_connection() -> None:
    global active_connections, total_connections
    with metrics_lock:
        active_connections += 1
        total_connections += 1


def _decrement_connection() -> None:
    global active_connections
    with metrics_lock:
        active_connections = max(0, active_connections - 1)


def _increment_error() -> None:
    global total_errors
    with metrics_lock:
        total_errors += 1
