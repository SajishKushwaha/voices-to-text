import sys
from pathlib import Path

from huggingface_hub import snapshot_download

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import Settings


def main() -> None:
    settings = Settings()
    settings.model_path.mkdir(parents=True, exist_ok=True)
    repo_id = f"Systran/faster-whisper-{settings.model_size}"

    print(
        f"Downloading Faster-Whisper model '{repo_id}' to {settings.model_path}"
    )
    snapshot_download(
        repo_id=repo_id,
        local_dir=settings.model_path,
        local_dir_use_symlinks=False,
    )
    print("Model is ready for local/offline use.")


if __name__ == "__main__":
    main()
