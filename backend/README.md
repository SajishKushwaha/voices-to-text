# Flask Faster-Whisper Backend

Local transcription API with no paid services.

## Setup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/download_model.py
python run.py
```

The default model is `tiny` with `int8` CPU compute. It is the fastest local choice for English and Hindi conversations. Use `base`, `small`, or `medium` for better accuracy if your server has more CPU/GPU budget.

## API

```bash
curl -X POST http://127.0.0.1:5001/api/transcribe \
  -F "audio=@sample.webm"
```

## Production

Install `ffmpeg` on the host. Faster-Whisper uses local model files once downloaded.

```bash
gunicorn "app:create_app()" --bind 127.0.0.1:5001 --workers 1 --threads 4 --timeout 180
```

Keep Flask behind a reverse proxy and expose only trusted origins with `CORS_ORIGINS`.
