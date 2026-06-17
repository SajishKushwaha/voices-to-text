import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread
from uuid import uuid4

from simple_websocket import ConnectionClosed

from ..config import Settings
from ..utils.files import delete_file_quietly
from .transcription_service import TranscriptionResult, TranscriptionService

LOGGER = logging.getLogger(__name__)
SUPPORTED_STREAM_MIME_TYPES = {
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "video/webm",
}


@dataclass(frozen=True)
class StreamStartMessage:
    mime_type: str
    chunk_ms: int


class StreamingTranscriptionSession:
    def __init__(
        self,
        ws,
        settings: Settings,
        service: TranscriptionService,
        model_semaphore: Semaphore,
    ) -> None:
        self.ws = ws
        self.settings = settings
        self.service = service
        self.model_semaphore = model_semaphore
        self.session_id = uuid4().hex
        self.started_at = time.monotonic()
        self.last_chunk_at = self.started_at
        self.last_transcribed_size = 0
        self.last_sent_text = ""
        self.byte_events: deque[tuple[float, int]] = deque()
        self.total_bytes = 0
        self.finalized = False
        self.mime_type = "audio/webm"
        self.chunk_ms = 750
        self.stop_event = Event()
        self.send_lock = Lock()
        self.transcribe_lock = Lock()
        self.worker: Thread | None = None
        self.temp_path: Path | None = None

    def start(self, message: StreamStartMessage) -> None:
        self.mime_type = message.mime_type
        self.chunk_ms = message.chunk_ms
        suffix = self._suffix_for_mime_type(self.mime_type)
        self.settings.stream_dir.mkdir(parents=True, exist_ok=True)
        self.temp_path = self.settings.stream_dir / f"{self.session_id}{suffix}"
        self.temp_path.touch()
        self.worker = Thread(target=self._run_worker, daemon=True)
        self.worker.start()
        self.send(
            {
                "type": "ready",
                "sessionId": self.session_id,
                "chunkMs": self.chunk_ms,
                "transcribeIntervalSeconds": self.settings.stream_transcribe_interval_seconds,
            }
        )

    def accept_chunk(self, payload: bytes) -> None:
        if self.finalized:
            raise StreamValidationError("Session is already finalized.", "SESSION_FINALIZED")

        if not payload:
            return

        if len(payload) > self.settings.stream_max_chunk_bytes:
            raise StreamValidationError("Audio chunk is too large.", "CHUNK_TOO_LARGE")

        elapsed = time.monotonic() - self.started_at
        if elapsed > self.settings.stream_max_session_seconds:
            raise StreamValidationError("Streaming session exceeded the time limit.", "SESSION_LIMIT")

        self._rate_limit(len(payload))

        if self.temp_path is None:
            raise StreamValidationError("Stream has not been started.", "STREAM_NOT_STARTED")

        with self.temp_path.open("ab") as file:
            file.write(payload)

        self.total_bytes += len(payload)
        self.last_chunk_at = time.monotonic()

    def finish(self) -> None:
        if self.finalized:
            return

        self.finalized = True
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=2)
        self._transcribe_and_send(is_final=True, force=True)

    def cleanup(self) -> None:
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=1)
        if self.temp_path is not None:
            delete_file_quietly(self.temp_path)

    def send(self, payload: dict) -> None:
        with self.send_lock:
            self.ws.send(json.dumps(payload))

    def _run_worker(self) -> None:
        interval = max(0.25, self.settings.stream_transcribe_interval_seconds)
        while not self.stop_event.wait(interval):
            try:
                self._transcribe_and_send(is_final=False)
            except ConnectionClosed:
                self.stop_event.set()
                return
            except Exception as error:
                LOGGER.debug(
                    "Partial transcription skipped for session %s: %s",
                    self.session_id,
                    error,
                    exc_info=True,
                )

    def _transcribe_and_send(self, is_final: bool, force: bool = False) -> None:
        if self.temp_path is None or not self.temp_path.exists():
            return

        current_size = self.temp_path.stat().st_size
        if current_size < 2048:
            return

        if not force and current_size == self.last_transcribed_size:
            return

        with self.transcribe_lock:
            current_size = self.temp_path.stat().st_size
            if not force and current_size == self.last_transcribed_size:
                return

            started_at = time.perf_counter()
            with self.model_semaphore:
                result = self.service.transcribe(self.temp_path, self.settings)

            text = result.text.strip()
            if not is_final and text == self.last_sent_text:
                self.last_transcribed_size = current_size
                return

            self.last_transcribed_size = current_size
            self.last_sent_text = text
            self.send(self._result_payload(result, is_final, started_at))

    def _result_payload(
        self,
        result: TranscriptionResult,
        is_final: bool,
        started_at: float,
    ) -> dict:
        return {
            "type": "final" if is_final else "partial",
            "sessionId": self.session_id,
            "text": result.text,
            "language": result.language,
            "detectedLanguage": result.detected_language,
            "languageFallbackUsed": result.language_fallback_used,
            "duration": result.duration,
            "processingTime": round(time.perf_counter() - started_at, 3),
            "receivedBytes": self.total_bytes,
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

    def _rate_limit(self, byte_count: int) -> None:
        now = time.monotonic()
        self.byte_events.append((now, byte_count))
        while self.byte_events and now - self.byte_events[0][0] > 1:
            self.byte_events.popleft()

        bytes_last_second = sum(size for _, size in self.byte_events)
        if bytes_last_second > self.settings.stream_max_bytes_per_second:
            raise StreamValidationError("Audio stream exceeded the rate limit.", "RATE_LIMITED")

    def _suffix_for_mime_type(self, mime_type: str) -> str:
        normalized = mime_type.split(";", 1)[0].strip().lower()
        if normalized in {"audio/ogg"}:
            return ".ogg"
        if normalized in {"audio/mp4"}:
            return ".m4a"
        if normalized in {"audio/mpeg"}:
            return ".mp3"
        if normalized in {"audio/wav"}:
            return ".wav"
        return ".webm"


class StreamValidationError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def parse_start_message(raw_message: str) -> StreamStartMessage:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as error:
        raise StreamValidationError("Invalid JSON control message.", "INVALID_JSON") from error

    if payload.get("type") != "start":
        raise StreamValidationError("Expected a start message.", "INVALID_START")

    mime_type = str(payload.get("mimeType") or "audio/webm").lower()
    if mime_type not in SUPPORTED_STREAM_MIME_TYPES:
        raise StreamValidationError("Unsupported audio stream type.", "UNSUPPORTED_AUDIO")

    try:
        chunk_ms = int(payload.get("chunkMs") or 750)
    except (TypeError, ValueError) as error:
        raise StreamValidationError("Invalid chunk duration.", "INVALID_CHUNK_MS") from error

    if chunk_ms < 250 or chunk_ms > 2000:
        raise StreamValidationError("Chunk duration must be between 250ms and 2000ms.", "INVALID_CHUNK_MS")

    return StreamStartMessage(mime_type=mime_type, chunk_ms=chunk_ms)
