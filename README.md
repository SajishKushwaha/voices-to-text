# Medical AI Dashboard

Production-ready self-hosted medical dashboard with a local `Voice to Text` module. The browser records audio with `MediaRecorder`, sends the file to a Python Flask endpoint, FFmpeg converts and enhances the audio, and Faster-Whisper Large-v3 transcribes or translates speech locally. Hindi, English, Hinglish, and medical vocabulary are supported without OpenAI API, Murf, Deepgram, AssemblyAI, or paid speech APIs.

## Architecture

```txt
User voice
  -> Next.js MediaRecorder
  -> Multipart audio upload
  -> Flask POST /api/transcribe
  -> FFmpeg validation/enhancement
  -> 16kHz mono PCM WAV
  -> Faster-Whisper Large-v3 + VAD
  -> Medical text cleanup
  -> Diagnostics dashboard

Lab report PDF
  -> Flask multipart upload
  -> pdfplumber text extraction
  -> OCR fallback for scanned PDFs
  -> Local structured medical extraction
  -> Editable hospital form
  -> SQLite persistence and audit logs
```

## Folder Structure

```txt
app/page.tsx                       Medical dashboard entry
components/medical/                Sidebar and two dashboard workspaces
components/voice/                  Shared waveform/status components
hooks/useStreamingTranscription.ts MediaRecorder + WebSocket hook
hooks/useVoiceRecorder.ts          MediaRecorder upload recorder hook
lib/medical/api.ts                 PDF/transcript API client
lib/transcription/                 Browser API clients and helpers
types/medical.ts                   Lab report and transcript types
types/transcription.ts             TypeScript response/message types
backend/app/database.py            SQLite schema and audit helpers
backend/app/routes/pdf.py          PDF extraction/review endpoints
backend/app/routes/transcripts.py  Transcript save/history endpoints
backend/app/routes/transcribe.py   Flask /api/transcribe endpoint
backend/app/routes/stream.py       Flask /api/transcribe/stream WebSocket
backend/app/services/audio_preprocessing_service.py FFmpeg validation/enhancement
backend/app/services/medical_text_postprocessor.py  Medical vocabulary cleanup
backend/app/services/entity_correction_service.py   Proper-noun fuzzy correction
backend/data/context_vocabulary.json                Names/cities/hospitals/doctors
backend/app/services/              Faster-Whisper and PDF extraction services
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
NEXT_PUBLIC_BACKEND_API_URL=http://127.0.0.1:5001
NEXT_PUBLIC_TRANSCRIBE_API_URL=http://127.0.0.1:5001/api/transcribe
NEXT_PUBLIC_TRANSCRIBE_WS_URL=ws://127.0.0.1:5001/api/transcribe/stream
NEXT_PUBLIC_MAX_RECORDING_SECONDS=180
NEXT_PUBLIC_STREAM_AUDIO_CHUNK_MS=750
NEXT_PUBLIC_STREAM_RECONNECT_MS=1200
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

For scanned PDF OCR fallback, install Tesseract and Poppler:

```bash
brew install tesseract poppler
```

Backend environment:

```bash
FLASK_PORT=5001
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
MAX_CONTENT_LENGTH_MB=25
DATABASE_PATH=data/medical_ai.db
PDF_UPLOAD_DIR=data/pdfs
STREAM_DIR=tmp/streams
STREAM_TRANSCRIBE_INTERVAL_SECONDS=0.8
STREAM_MAX_CHUNK_BYTES=1048576
STREAM_MAX_BYTES_PER_SECOND=1048576
STREAM_MAX_SESSION_SECONDS=1800
WHISPER_MAX_WORKERS=1
WHISPER_MODEL_SIZE=large-v3
WHISPER_MODEL_PATH=models/faster-whisper-large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=3
WHISPER_VAD_FILTER=true
WHISPER_NO_SPEECH_THRESHOLD=0.6
WHISPER_INITIAL_PROMPT=Transcribe exactly what is spoken. Do not translate. The speaker may use Hindi, English, Hinglish, and medical terms.
WHISPER_SUPPORTED_LANGUAGES=en,hi
WHISPER_RETRY_UNSUPPORTED_LANGUAGE=true
WHISPER_FALLBACK_LANGUAGE=hi
```

`large-v3` is the accuracy-first default for Hindi, English, Hinglish, and medical dictation. It is slower than small models. Use GPU settings such as `WHISPER_DEVICE=cuda` and `WHISPER_COMPUTE_TYPE=float16` when available.

For short clips, Whisper can occasionally mis-detect English or Hindi as another language. The UI sends a language mode with every upload, so choose `Hindi` for Hindi/Hinglish dictation and `English` for English dictation. Use `Auto` only when the language genuinely changes between recordings.

## Run Both Services

```bash
npm run dev:all
```

Next.js runs at `http://localhost:3000`. Flask runs at `http://127.0.0.1:5001`.

## Voice-to-Text API

`POST /api/transcribe` on Flask accepts `multipart/form-data` with the browser audio file in the `audio` field.

```bash
curl -X POST http://127.0.0.1:5001/api/transcribe \
  -F "audio=@recording.webm"
```

Successful response:

```json
{
  "success": true,
  "text": "transcribed user speech"
}
```

Error response:

```json
{
  "success": false,
  "error": "Unsupported audio file type.",
  "code": "UNSUPPORTED_AUDIO"
}
```

The endpoint validates file type and size, writes uploads to a temporary directory, transcribes with Faster-Whisper, returns JSON, and deletes temporary files in a `finally` block. Runtime transcription is fully local after the model has been downloaded.

## Legacy Real-Time WebSocket API

The older streaming client can connect to:

```txt
ws://127.0.0.1:5001/api/transcribe/stream
```

Client start message:

```json
{
  "type": "start",
  "mimeType": "audio/webm;codecs=opus",
  "chunkMs": 750
}
```

After the start message, the browser sends binary MediaRecorder chunks every `500ms` to `1000ms`. Flask appends those chunks to a per-session temporary audio file and periodically runs Faster-Whisper against the growing buffer. The server streams back:

```json
{
  "type": "partial",
  "sessionId": "session-id",
  "text": "live partial text",
  "language": "en",
  "processingTime": 0.42
}
```

When the browser stops recording, it sends:

```json
{ "type": "stop" }
```

The server returns a final message:

```json
{
  "type": "final",
  "sessionId": "session-id",
  "text": "confirmed transcript",
  "language": "en",
  "processingTime": 0.58
}
```

Faster-Whisper does not expose true token-by-token streaming. This implementation uses a streaming-friendly architecture: WebSocket audio transport, bounded chunk queues, rate limits, per-session cleanup, and low-latency repeated transcription of the current audio buffer.

## PDF Extraction API

Upload and extract a lab report:

```bash
curl -X POST http://127.0.0.1:5001/api/pdf/extract \
  -F "pdf=@lab-report.pdf"
```

The output includes the requested structured shape plus additional review metadata:

```json
{
  "patientName": "",
  "age": "",
  "gender": "",
  "reportDate": "",
  "tests": []
}
```

Save reviewed data:

```txt
POST /api/pdf/reports/{reportId}/review
```

Save voice transcript:

```txt
POST /api/transcripts
```

SQLite tables are created automatically at `DATABASE_PATH`:

```txt
transcripts
pdf_reports
review_history
audit_logs
```

## Legacy Upload API

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

The backend validates file type and size, writes uploads to a temporary directory, transcribes with Faster-Whisper, returns structured JSON, and deletes temporary files in a `finally` block. This route is kept for tests, curl usage, and non-streaming clients.

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
gunicorn "app:create_app()" --bind 127.0.0.1:5001 --workers 1 --threads 4 --timeout 600
```

Place both services behind a reverse proxy such as Nginx. Keep Flask private to your network or server, and set `CORS_ORIGINS` to the exact frontend domains. Pre-download the Faster-Whisper model with `python scripts/download_model.py` during deployment so transcription does not need internet access at runtime.

Nginx upload proxy example:

```nginx
location /api/transcribe {
  proxy_pass http://127.0.0.1:5001;
  proxy_set_header Host $host;
  client_max_body_size 25m;
}
```

Health endpoint:

```txt
GET http://127.0.0.1:5001/api/health
```

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
