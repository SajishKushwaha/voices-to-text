from pathlib import Path

ALLOWED_EXTENSIONS = {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".mp4", ".mpeg"}
ALLOWED_MIME_PREFIXES = ("audio/",)
ALLOWED_MIME_TYPES = {
    "application/octet-stream",
    "video/mp4",
    "video/webm",
}


def is_allowed_audio_file(filename: str, mimetype: str | None) -> bool:
    suffix = Path(filename).suffix.lower()
    valid_extension = suffix in ALLOWED_EXTENSIONS
    valid_mime = bool(
        mimetype
        and (mimetype.startswith(ALLOWED_MIME_PREFIXES) or mimetype in ALLOWED_MIME_TYPES)
    )
    return valid_extension and valid_mime


def delete_file_quietly(path: Path) -> None:
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except OSError:
        pass
