import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("FLASK_ENV", "production")
    host: str = os.getenv("FLASK_HOST", "127.0.0.1")
    port: int = int(os.getenv("FLASK_PORT", "5001"))
    cors_origins: list[str] = field(
        default_factory=lambda: _csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            )
        )
    )
    max_content_length_mb: int = int(os.getenv("MAX_CONTENT_LENGTH_MB", "25"))
    upload_dir: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "tmp/uploads")
    ffmpeg_binary: str = os.getenv("FFMPEG_BINARY", "ffmpeg")
    ffprobe_binary: str = os.getenv("FFPROBE_BINARY", "ffprobe")
    audio_preprocessing_enabled: bool = (
        os.getenv("AUDIO_PREPROCESSING_ENABLED", "true").lower() == "true"
    )
    audio_preprocessing_timeout_seconds: int = int(
        os.getenv("AUDIO_PREPROCESSING_TIMEOUT_SECONDS", "30")
    )
    preprocessed_sample_rate: int = int(os.getenv("PREPROCESSED_SAMPLE_RATE", "16000"))
    audio_filter: str = os.getenv(
        "AUDIO_FILTER",
        "highpass=f=70,lowpass=f=7600,afftdn=nf=-20,loudnorm=I=-18:TP=-1.5:LRA=11,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.2:stop_periods=-1:stop_threshold=-45dB:stop_silence=0.5",
    )
    min_audio_duration_seconds: float = float(os.getenv("MIN_AUDIO_DURATION_SECONDS", "0"))
    max_audio_duration_seconds: float = float(os.getenv("MAX_AUDIO_DURATION_SECONDS", "180"))
    stream_dir: Path = BASE_DIR / os.getenv("STREAM_DIR", "tmp/streams")
    database_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/medical_ai.db")
    pdf_upload_dir: Path = BASE_DIR / os.getenv("PDF_UPLOAD_DIR", "data/pdfs")
    context_vocabulary_path: Path = BASE_DIR / os.getenv(
        "CONTEXT_VOCABULARY_PATH",
        "data/context_vocabulary.json",
    )
    stream_transcribe_interval_seconds: float = float(
        os.getenv("STREAM_TRANSCRIBE_INTERVAL_SECONDS", "0.8")
    )
    stream_max_chunk_bytes: int = int(os.getenv("STREAM_MAX_CHUNK_BYTES", "1048576"))
    stream_max_bytes_per_second: int = int(
        os.getenv("STREAM_MAX_BYTES_PER_SECOND", "1048576")
    )
    stream_max_session_seconds: int = int(
        os.getenv("STREAM_MAX_SESSION_SECONDS", "1800")
    )
    whisper_max_workers: int = int(os.getenv("WHISPER_MAX_WORKERS", "1"))
    model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    model_path: Path = BASE_DIR / os.getenv(
        "WHISPER_MODEL_PATH", "models/faster-whisper-large-v3"
    )
    device: str = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    beam_size: int = int(os.getenv("WHISPER_BEAM_SIZE", "10"))
    best_of: int = int(os.getenv("WHISPER_BEST_OF", "10"))
    patience: float = float(os.getenv("WHISPER_PATIENCE", "1.0"))
    log_prob_threshold: float = float(os.getenv("WHISPER_LOG_PROB_THRESHOLD", "-1.0"))
    compression_ratio_threshold: float = float(
        os.getenv("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4")
    )
    low_confidence_logprob_threshold: float = float(
        os.getenv("WHISPER_LOW_CONFIDENCE_LOGPROB_THRESHOLD", "-0.85")
    )
    vad_filter: bool = os.getenv("WHISPER_VAD_FILTER", "true").lower() == "true"
    vad_min_silence_duration_ms: int = int(
        os.getenv("WHISPER_VAD_MIN_SILENCE_DURATION_MS", "500")
    )
    vad_speech_pad_ms: int = int(os.getenv("WHISPER_VAD_SPEECH_PAD_MS", "250"))
    no_speech_threshold: float = float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.6"))
    hallucination_silence_threshold: float = float(
        os.getenv("WHISPER_HALLUCINATION_SILENCE_THRESHOLD", "2.0")
    )
    temperature: float = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
    # Instruction-like initial prompts can be repeated as hallucinated speech.
    # Recognition hints belong in hotwords instead.
    initial_prompt: str = os.getenv("WHISPER_INITIAL_PROMPT", "")
    english_prompt: str = os.getenv("WHISPER_ENGLISH_PROMPT", "")
    translation_prompt: str = os.getenv("WHISPER_TRANSLATION_PROMPT", "")
    hotwords: str = os.getenv(
        "WHISPER_HOTWORDS",
        "Hemoglobin HbA1c Creatinine Platelet WBC RBC Sodium Potassium Cholesterol Triglycerides TSH T3 T4 Diabetes Hypertension Cardiology Neurology Gastroenterology Prescription Consultation Admission Discharge",
    )
    use_hotwords: bool = os.getenv("WHISPER_USE_HOTWORDS", "false").lower() == "true"
    entity_name_threshold: int = int(os.getenv("ENTITY_NAME_THRESHOLD", "80"))
    entity_location_threshold: int = int(os.getenv("ENTITY_LOCATION_THRESHOLD", "65"))
    entity_hospital_threshold: int = int(os.getenv("ENTITY_HOSPITAL_THRESHOLD", "82"))
    entity_doctor_threshold: int = int(os.getenv("ENTITY_DOCTOR_THRESHOLD", "82"))
    entity_medical_threshold: int = int(os.getenv("ENTITY_MEDICAL_THRESHOLD", "82"))
    confirmation_alternative_count: int = int(
        os.getenv("CONFIRMATION_ALTERNATIVE_COUNT", "3")
    )
    word_low_confidence_threshold: float = float(
        os.getenv("WORD_LOW_CONFIDENCE_THRESHOLD", "0.65")
    )
    fallback_language: str = os.getenv("WHISPER_FALLBACK_LANGUAGE", "hi")
    retry_unsupported_language: bool = (
        os.getenv("WHISPER_RETRY_UNSUPPORTED_LANGUAGE", "true").lower() == "true"
    )
    supported_languages: list[str] = field(
        default_factory=lambda: _csv(os.getenv("WHISPER_SUPPORTED_LANGUAGES", "en,hi"))
    )

    @property
    def debug(self) -> bool:
        return self.env == "development"

    @property
    def max_content_length_bytes(self) -> int:
        return self.max_content_length_mb * 1024 * 1024
