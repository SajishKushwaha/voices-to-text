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
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    words: list["WordResult"] | None = None


@dataclass(frozen=True)
class WordResult:
    word: str
    start: float
    end: float
    probability: float
    confidence_score: int
    low_confidence: bool


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    duration: float
    segments: list[SegmentResult]
    detected_language: str | None = None
    language_fallback_used: bool = False
    avg_logprob: float | None = None
    low_confidence: bool = False
    words: list[WordResult] | None = None


class TranscriptionService:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_key: tuple[str, str, str] | None = None
        self._lock = Lock()

    def transcribe(
        self,
        audio_path: Path,
        settings: Settings,
        language: str | None = None,
        task: str = "transcribe",
        context_prompt: str = "",
        context_hotwords: str = "",
    ) -> TranscriptionResult:
        model = self._get_model(settings)
        result = self._transcribe_once(
            audio_path,
            model,
            settings,
            language=language,
            task=task,
            context_prompt=context_prompt,
            context_hotwords=context_hotwords,
        )

        if (
            language is None
            and settings.retry_unsupported_language
            and settings.supported_languages
            and result.language not in settings.supported_languages
        ):
            fallback_language = self._resolve_fallback_language(settings)
            fallback_result = self._transcribe_once(
                audio_path,
                model,
                settings,
                language=fallback_language,
                task=task,
                context_prompt=context_prompt,
                context_hotwords=context_hotwords,
            )
            return TranscriptionResult(
                text=fallback_result.text,
                language=fallback_language,
                duration=fallback_result.duration,
                segments=fallback_result.segments,
                detected_language=result.language,
                language_fallback_used=True,
                avg_logprob=fallback_result.avg_logprob,
                low_confidence=fallback_result.low_confidence,
                words=fallback_result.words,
            )

        if settings.supported_languages and result.language not in settings.supported_languages:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                duration=result.duration,
                segments=result.segments,
                detected_language=result.language,
                language_fallback_used=False,
                avg_logprob=result.avg_logprob,
                low_confidence=result.low_confidence,
                words=result.words,
            )

        return result

    def _transcribe_once(
        self,
        audio_path: Path,
        model: WhisperModel,
        settings: Settings,
        language: str | None = None,
        task: str = "transcribe",
        context_prompt: str = "",
        context_hotwords: str = "",
    ) -> TranscriptionResult:
        segments_iter, info = model.transcribe(
            str(audio_path),
            beam_size=settings.beam_size,
            best_of=settings.best_of,
            patience=settings.patience,
            compression_ratio_threshold=settings.compression_ratio_threshold,
            log_prob_threshold=settings.log_prob_threshold,
            condition_on_previous_text=False,
            language=language,
            task=task,
            vad_filter=settings.vad_filter,
            vad_parameters={
                "min_silence_duration_ms": settings.vad_min_silence_duration_ms,
                "speech_pad_ms": settings.vad_speech_pad_ms,
            },
            word_timestamps=True,
            initial_prompt=self._resolve_prompt(
                settings,
                task,
                language,
                context_prompt,
            ),
            hotwords=(
                " ".join(
                    value for value in [settings.hotwords, context_hotwords] if value
                )
                if settings.use_hotwords
                else None
            ),
            no_speech_threshold=settings.no_speech_threshold,
            hallucination_silence_threshold=settings.hallucination_silence_threshold,
            temperature=settings.temperature,
        )
        detected_language = info.language or language or "unknown"
        segments: list[SegmentResult] = []
        words: list[WordResult] = []
        for index, segment in enumerate(segments_iter):
            segment_words = [
                WordResult(
                    word=word.word.strip(),
                    start=round(float(word.start or 0.0), 3),
                    end=round(float(word.end or 0.0), 3),
                    probability=round(float(word.probability or 0.0), 3),
                    confidence_score=round(float(word.probability or 0.0) * 100),
                    low_confidence=bool(
                        float(word.probability or 0.0)
                        < settings.word_low_confidence_threshold
                    ),
                )
                for word in (segment.words or [])
                if word.word.strip()
            ]
            words.extend(segment_words)
            segments.append(
                SegmentResult(
                    id=index,
                    start=round(float(segment.start), 3),
                    end=round(float(segment.end), 3),
                    text=segment.text.strip(),
                    avg_logprob=round(float(getattr(segment, "avg_logprob", 0)), 3)
                    if getattr(segment, "avg_logprob", None) is not None
                    else None,
                    no_speech_prob=round(
                        float(getattr(segment, "no_speech_prob", 0)), 3
                    )
                    if getattr(segment, "no_speech_prob", None) is not None
                    else None,
                    words=segment_words,
                )
            )
        text = " ".join(segment.text for segment in segments).strip()
        avg_logprob = self._average_logprob(segments)

        return TranscriptionResult(
            text=text,
            language=str(language or detected_language),
            duration=round(float(info.duration or 0.0), 3),
            segments=segments,
            detected_language=str(detected_language),
            avg_logprob=avg_logprob,
            low_confidence=bool(
                avg_logprob is not None
                and avg_logprob < settings.low_confidence_logprob_threshold
            ),
            words=words,
        )

    def _resolve_fallback_language(self, settings: Settings) -> str:
        if settings.fallback_language in settings.supported_languages:
            return settings.fallback_language

        if settings.supported_languages:
            return settings.supported_languages[0]

        return settings.fallback_language or "en"

    def _resolve_prompt(
        self,
        settings: Settings,
        task: str,
        language: str | None,
        context_prompt: str = "",
    ) -> str | None:
        if task == "translate":
            base_prompt = settings.translation_prompt
        elif language == "en":
            base_prompt = settings.english_prompt
        else:
            base_prompt = settings.initial_prompt

        # Context vocabulary is supplied through Faster-Whisper hotwords.
        # Putting instructions or long vocabulary lists in initial_prompt can
        # cause Whisper to emit the prompt itself during silence.
        return base_prompt.strip() or None

    def _average_logprob(self, segments: list[SegmentResult]) -> float | None:
        values = [
            segment.avg_logprob
            for segment in segments
            if segment.avg_logprob is not None
        ]
        if not values:
            return None

        return round(float(sum(values) / len(values)), 3)

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
