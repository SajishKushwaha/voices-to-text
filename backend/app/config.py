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
    model_size: str = os.getenv("WHISPER_MODEL_SIZE", "tiny")
    model_path: Path = BASE_DIR / os.getenv(
        "WHISPER_MODEL_PATH", "models/faster-whisper-tiny"
    )
    device: str = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    beam_size: int = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
    vad_filter: bool = os.getenv("WHISPER_VAD_FILTER", "true").lower() == "true"
    fallback_language: str = os.getenv("WHISPER_FALLBACK_LANGUAGE", "en")
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
