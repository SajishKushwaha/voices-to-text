# Local Voice AI

Self-hosted voice tooling with zero paid APIs. The main app records voice in Next.js, sends audio to Flask, transcribes locally with Faster-Whisper, and displays the text in a WhatsApp-style chat UI. The project also keeps the Piper TTS integration under `/api/tts`.

## Architecture

```txt
User voice
  -> Next.js MediaRecorder
  -> Flask multipart upload
  -> Faster-Whisper local transcription
  -> JSON response
  -> Chat bubble in Next.js
```

## Folder Structure

```txt
app/page.tsx                       Voice chat page
components/voice/                  Recorder, waveform, chat bubbles
hooks/useVoiceRecorder.ts          MediaRecorder hook
lib/transcription/                 Browser API client and helpers
types/transcription.ts             TypeScript response/message types
backend/app/routes/transcribe.py   Flask /api/transcribe endpoint
backend/app/services/              Faster-Whisper service
backend/scripts/download_model.py  Local model preparation
app/api/tts/route.ts               Piper TTS endpoint
voices/                            Piper voice models
public/generated/tts/              Generated TTS audio files
```

## Frontend Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Frontend environment:

```bash
NEXT_PUBLIC_TRANSCRIBE_API_URL=http://127.0.0.1:5001/api/transcribe
NEXT_PUBLIC_MAX_RECORDING_SECONDS=180
```

## Flask + Faster-Whisper Setup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/download_model.py
python run.py
```

Install FFmpeg if it is not already available:

```bash
brew install ffmpeg
```

Backend environment:

```bash
FLASK_PORT=5001
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
MAX_CONTENT_LENGTH_MB=25
WHISPER_MODEL_SIZE=tiny
WHISPER_MODEL_PATH=models/faster-whisper-tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=1
WHISPER_VAD_FILTER=true
WHISPER_SUPPORTED_LANGUAGES=en,hi
WHISPER_RETRY_UNSUPPORTED_LANGUAGE=true
WHISPER_FALLBACK_LANGUAGE=en
```

`tiny` with `int8` CPU compute is the fastest default for local English/Hindi conversations. Use `base`, `small`, or `medium` for better accuracy on stronger servers, or GPU settings such as `WHISPER_DEVICE=cuda` and `WHISPER_COMPUTE_TYPE=float16` when available.

For short clips, Whisper can occasionally mis-detect English or Hindi as another language. With `WHISPER_RETRY_UNSUPPORTED_LANGUAGE=true`, unsupported detections are retried with `WHISPER_FALLBACK_LANGUAGE` instead of failing the chat bubble.

## Run Both Services

```bash
npm run dev:all
```

Next.js runs at `http://localhost:3000`. Flask runs at `http://127.0.0.1:5001`.

## Transcription API

`POST /api/transcribe` on Flask accepts `multipart/form-data`.

```bash
curl -X POST http://127.0.0.1:5001/api/transcribe \
  -F "audio=@recording.webm"
```

Response:

```json
{
  "success": true,
  "text": "Transcribed speech",
  "language": "en",
  "processingTime": 1.2
}
```

The backend validates file type and size, writes uploads to a temporary directory, transcribes with Faster-Whisper, returns structured JSON, and deletes temporary files in a `finally` block.

## Production Deployment

Build and run Next.js:

```bash
npm run build
npm run start
```

Run Flask with Gunicorn:

```bash
cd backend
. .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:5001 --workers 1 --threads 4 --timeout 180
```

Place both services behind a reverse proxy such as Nginx. Keep Flask private to your network or server, and set `CORS_ORIGINS` to the exact frontend domains. Pre-download the Faster-Whisper model with `python scripts/download_model.py` during deployment so transcription does not need internet access at runtime.

## Piper TTS

Install local Piper and English/Hindi voices:

```bash
npm run piper:install
```

TTS endpoint:

```txt
POST /api/tts
```

Piper voice models live in `/voices`, and generated audio is stored in `public/generated/tts`.
