import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Settings
from .services.audio_preprocessing_service import AudioPreprocessingService
from .services.context_vocabulary_service import ContextVocabularyService
from .services.entity_correction_service import EntityCorrectionService
from .services.medical_text_postprocessor import MedicalTextPostProcessor
from .services.transcription_service import TranscriptionService
from .utils.files import delete_file_quietly, is_allowed_audio_file

logger = logging.getLogger(__name__)
settings = Settings()
service = TranscriptionService()
audio_preprocessor = AudioPreprocessingService()
postprocessor = MedicalTextPostProcessor()
vocabulary_service = ContextVocabularyService()
entity_correction_service = EntityCorrectionService()


class TranscribeResponse(BaseModel):
    success: bool
    text: str
    rawText: str | None = None
    cleanedText: str | None = None
    language: str | None = None
    detectedLanguage: str | None = None
    avgLogprob: float | None = None
    lowConfidence: bool = False
    confidenceScore: int | None = None
    audioQualityScore: int | None = None
    audioDiagnostics: dict | None = None
    postProcessing: dict | None = None
    confirmations: list[dict] | None = None
    words: list[dict] | None = None
    processingTime: float | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str


app = FastAPI(
    title="Local Voice-to-Text API",
    description="Self-hosted Faster-Whisper transcription for browser audio uploads.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"success": True, "status": "ok"}


@app.post(
    "/transcribe",
    response_model=TranscribeResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    task: str = Form("transcribe"),
):
    started_at = time.perf_counter()
    validate_upload(audio)
    selected_language = validate_language(language)
    selected_task = validate_task(task)

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "recording.webm").suffix.lower() or ".webm"
    temp_path = settings.upload_dir / f"{uuid4().hex}{suffix}"
    processed_path = temp_path
    audio_result = None

    try:
        await write_upload(audio, temp_path)
        logger.info("Transcribing upload %s", temp_path.name)
        audio_result = audio_preprocessor.preprocess(temp_path, settings)
        processed_path = audio_result.audio_path
        vocabulary = vocabulary_service.load(settings)
        result = service.transcribe(
            processed_path,
            settings,
            language=selected_language,
            task=selected_task,
            context_prompt=vocabulary_service.recognition_prompt(vocabulary),
            context_hotwords=vocabulary_service.hotwords(vocabulary),
        )
        entity_corrected = entity_correction_service.correct(
            result.text,
            vocabulary,
            settings,
        )
        postprocessed = postprocessor.process(entity_corrected.text)
        processing_time = round(time.perf_counter() - started_at, 3)
        logger.info(
            "Transcribed %s in %.3fs",
            temp_path.name,
            processing_time,
        )
        return {
            "success": True,
            "text": postprocessed.cleaned_text,
            "rawText": result.text,
            "cleanedText": postprocessed.cleaned_text,
            "language": result.language,
            "detectedLanguage": result.detected_language,
            "avgLogprob": result.avg_logprob,
            "lowConfidence": bool(result.low_confidence),
            "confidenceScore": confidence_from_logprob(result.avg_logprob),
            "audioQualityScore": audio_result.diagnostics.quality_score
            if audio_result
            else None,
            "audioDiagnostics": diagnostics_payload(audio_result),
            "postProcessing": {
                "corrections": sorted(set(postprocessed.corrections)),
                "entityCorrections": [
                    {
                        "original": correction.original,
                        "corrected": correction.corrected,
                        "category": correction.category,
                        "similarity": correction.similarity,
                        "requiresConfirmation": bool(
                            correction.requires_confirmation
                        ),
                    }
                    for correction in entity_corrected.corrections
                ],
            },
            "confirmations": [
                {
                    "id": confirmation.id,
                    "fieldType": confirmation.field_type,
                    "original": confirmation.original,
                    "suggested": confirmation.suggested,
                    "alternatives": confirmation.alternatives,
                    "confidence": confirmation.confidence,
                }
                for confirmation in entity_corrected.confirmations
            ],
            "words": [
                {
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability,
                    "confidenceScore": word.confidence_score,
                    "lowConfidence": bool(word.low_confidence),
                }
                for word in (result.words or [])
            ],
            "processingTime": processing_time,
        }
    except HTTPException:
        raise
    except ValueError as error:
        logger.warning("Transcription validation failed: %s", error)
        raise http_error(str(error), "TRANSCRIPTION_VALIDATION_FAILED", 400) from error
    except Exception as error:
        logger.exception("Transcription failed: %s", error)
        raise http_error("Unable to transcribe audio.", "TRANSCRIPTION_FAILED", 500) from error
    finally:
        await audio.close()
        if processed_path != temp_path:
            delete_file_quietly(processed_path)
        delete_file_quietly(temp_path)


def validate_upload(audio: UploadFile) -> None:
    if not audio.filename:
        raise http_error("Audio filename is required.", "INVALID_FILENAME", 400)

    if not is_allowed_audio_file(audio.filename, audio.content_type):
        raise http_error("Unsupported audio file type.", "UNSUPPORTED_AUDIO", 415)


def validate_language(language: str) -> str | None:
    normalized_language = language.strip().lower()
    if normalized_language in {"", "auto"}:
        return None

    if normalized_language not in settings.supported_languages:
        raise http_error("Supported languages are: auto, en, hi.", "INVALID_LANGUAGE", 400)

    return normalized_language


def validate_task(task: str) -> str:
    normalized_task = task.strip().lower()
    if normalized_task in {"", "transcribe"}:
        return "transcribe"

    if normalized_task == "translate":
        return "translate"

    raise http_error("Supported tasks are: transcribe, translate.", "INVALID_TASK", 400)


def confidence_from_logprob(avg_logprob: float | None) -> int | None:
    if avg_logprob is None:
        return None

    return max(0, min(100, round((avg_logprob + 1.5) / 1.5 * 100)))


def diagnostics_payload(audio_result):
    if not audio_result:
        return None

    diagnostics = audio_result.diagnostics
    return {
        "inputFormat": diagnostics.input_format,
        "inputCodec": diagnostics.input_codec,
        "inputSampleRate": diagnostics.input_sample_rate,
        "inputChannels": diagnostics.input_channels,
        "inputDuration": diagnostics.input_duration,
        "inputSizeBytes": diagnostics.input_size_bytes,
        "outputFormat": diagnostics.output_format,
        "outputCodec": diagnostics.output_codec,
        "outputSampleRate": diagnostics.output_sample_rate,
        "outputChannels": diagnostics.output_channels,
        "outputDuration": diagnostics.output_duration,
        "outputSizeBytes": diagnostics.output_size_bytes,
        "enhancementApplied": bool(diagnostics.enhancement_applied),
        "qualityScore": diagnostics.quality_score,
        "warnings": diagnostics.warnings,
    }


async def write_upload(audio: UploadFile, destination: Path) -> None:
    max_bytes = settings.max_content_length_bytes
    total_bytes = 0

    with destination.open("wb") as output:
        while chunk := await audio.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise http_error("Audio file is too large.", "FILE_TOO_LARGE", 413)
            output.write(chunk)

    if total_bytes == 0:
        raise http_error("Uploaded audio is empty.", "EMPTY_AUDIO", 400)


def http_error(message: str, code: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "error": message, "code": code},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": str(exc.detail),
            "code": "REQUEST_FAILED",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Unexpected server error.",
            "code": "INTERNAL_SERVER_ERROR",
        },
    )
