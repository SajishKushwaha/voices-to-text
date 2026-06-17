import time
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..config import Settings
from ..services.audio_preprocessing_service import AudioPreprocessingService
from ..services.context_vocabulary_service import ContextVocabularyService
from ..services.entity_correction_service import EntityCorrectionService
from ..services.medical_text_postprocessor import MedicalTextPostProcessor
from ..services.transcription_service import TranscriptionService
from ..utils.files import delete_file_quietly, is_allowed_audio_file

transcribe_bp = Blueprint("transcribe", __name__)
service = TranscriptionService()
audio_preprocessor = AudioPreprocessingService()
postprocessor = MedicalTextPostProcessor()
vocabulary_service = ContextVocabularyService()
entity_correction_service = EntityCorrectionService()


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
    try:
        language = validate_language(request.form.get("language", "auto"), settings)
        task = validate_task(request.form.get("task", "transcribe"))
    except ValueError as error:
        return error_response(str(error), "INVALID_REQUEST", 400)

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(secure_filename(audio.filename or "recording.webm")).suffix.lower()
    temp_path = settings.upload_dir / f"{uuid4().hex}{suffix}"
    processed_path = temp_path
    audio_result = None

    try:
        audio.save(temp_path)
        current_app.logger.info("Transcribing upload %s", temp_path.name)
        audio_result = audio_preprocessor.preprocess(temp_path, settings)
        processed_path = audio_result.audio_path
        vocabulary = vocabulary_service.load(settings)
        result = service.transcribe(
            processed_path,
            settings,
            language=language,
            task=task,
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
        confidence_score = confidence_from_logprob(result.avg_logprob)

        return jsonify(
            {
                "success": True,
                "text": postprocessed.cleaned_text,
                "rawText": result.text,
                "cleanedText": postprocessed.cleaned_text,
                "language": result.language,
                "detectedLanguage": result.detected_language,
                "languageFallbackUsed": bool(result.language_fallback_used),
                "avgLogprob": result.avg_logprob,
                "lowConfidence": bool(result.low_confidence),
                "confidenceScore": confidence_score,
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
                "duration": result.duration,
                "segments": [
                    {
                        "id": segment.id,
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                        "avgLogprob": segment.avg_logprob,
                        "noSpeechProb": segment.no_speech_prob,
                        "words": [
                            {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "probability": word.probability,
                                "confidenceScore": word.confidence_score,
                                "lowConfidence": bool(word.low_confidence),
                            }
                            for word in (segment.words or [])
                        ],
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
        if processed_path != temp_path:
            delete_file_quietly(processed_path)
        delete_file_quietly(temp_path)


def validate_audio(audio: FileStorage):
    if not audio.filename:
        return error_response("Audio filename is required.", "INVALID_FILENAME", 400)

    if not is_allowed_audio_file(audio.filename, audio.mimetype):
        return error_response("Unsupported audio file type.", "UNSUPPORTED_AUDIO", 415)

    return None


def validate_language(language: str, settings: Settings):
    normalized_language = language.strip().lower()
    if normalized_language in {"", "auto"}:
        return None

    if normalized_language not in settings.supported_languages:
        raise ValueError("Supported languages are: auto, en, hi.")

    return normalized_language


def validate_task(task: str):
    normalized_task = task.strip().lower()
    if normalized_task in {"", "transcribe"}:
        return "transcribe"

    if normalized_task == "translate":
        return "translate"

    raise ValueError("Supported tasks are: transcribe, translate.")


def confidence_from_logprob(avg_logprob: float | None) -> int | None:
    if avg_logprob is None:
        return None

    # Whisper avg_logprob is usually <= 0. Map [-1.5, 0] to [0, 100].
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


def error_response(message: str, code: str, status: int):
    return jsonify({"success": False, "error": message, "code": code}), status
