from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from faster_whisper import WhisperModel

from ..config import Settings


@dataclass(frozen=True)
class SegmentResult:
    id: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    duration: float
    segments: list[SegmentResult]
    detected_language: str | None = None
    language_fallback_used: bool = False


class TranscriptionService:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_key: tuple[str, str, str] | None = None
        self._lock = Lock()

    def transcribe(self, audio_path: Path, settings: Settings) -> TranscriptionResult:
        model = self._get_model(settings)
        result = self._transcribe_once(audio_path, model, settings)

        if (
            settings.retry_unsupported_language
            and settings.supported_languages
            and result.language not in settings.supported_languages
        ):
            fallback_language = self._resolve_fallback_language(settings)
            fallback_result = self._transcribe_once(
                audio_path,
                model,
                settings,
                language=fallback_language,
            )
            return TranscriptionResult(
                text=fallback_result.text,
                language=fallback_language,
                duration=fallback_result.duration,
                segments=fallback_result.segments,
                detected_language=result.language,
                language_fallback_used=True,
            )

        if settings.supported_languages and result.language not in settings.supported_languages:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                duration=result.duration,
                segments=result.segments,
                detected_language=result.language,
                language_fallback_used=False,
            )

        return result

    def _transcribe_once(
        self,
        audio_path: Path,
        model: WhisperModel,
        settings: Settings,
        language: str | None = None,
    ) -> TranscriptionResult:
        segments_iter, info = model.transcribe(
            str(audio_path),
            beam_size=settings.beam_size,
            condition_on_previous_text=False,
            language=language,
            vad_filter=settings.vad_filter,
            word_timestamps=False,
        )
        detected_language = info.language or language or "unknown"
        segments = [
            SegmentResult(
                id=index,
                start=round(segment.start, 3),
                end=round(segment.end, 3),
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments_iter)
        ]
        text = " ".join(segment.text for segment in segments).strip()

        return TranscriptionResult(
            text=text,
            language=language or detected_language,
            duration=round(info.duration or 0.0, 3),
            segments=segments,
            detected_language=detected_language,
        )

    def _resolve_fallback_language(self, settings: Settings) -> str:
        if settings.fallback_language in settings.supported_languages:
            return settings.fallback_language

        if settings.supported_languages:
            return settings.supported_languages[0]

        return settings.fallback_language or "en"

    def _get_model(self, settings: Settings) -> WhisperModel:
        if not settings.model_path.exists():
            raise ValueError(
                f"Local Faster-Whisper model not found at {settings.model_path}. "
                "Run `python scripts/download_model.py` before starting production."
            )

        model_source = str(settings.model_path)
        model_key = (model_source, settings.device, settings.compute_type)

        if self._model and self._model_key == model_key:
            return self._model

        with self._lock:
            if self._model and self._model_key == model_key:
                return self._model

            self._model = WhisperModel(
                model_source,
                device=settings.device,
                compute_type=settings.compute_type,
            )
            self._model_key = model_key
            return self._model
