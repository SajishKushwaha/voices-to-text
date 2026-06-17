# Flask Voice-to-Text Backend

Self-hosted speech recognition backend for Hindi, English, Hinglish, and medical dictation. The pipeline uses FFmpeg audio validation/enhancement, Faster-Whisper `large-v3`, VAD filtering, medical vocabulary cleanup, confidence scoring, and diagnostics. No paid APIs are used.

## Recognition Pipeline

```txt
MediaRecorder upload
  -> FFprobe validation
  -> FFmpeg 16kHz mono PCM WAV enhancement
  -> Large-v3 with beam_size=10, VAD, contextual prompt, and hotwords
  -> word-level confidence scoring
  -> entity-aware fuzzy correction
  -> medical spelling cleanup
  -> critical-field confirmation response
```

Known names, cities, hospitals, doctors, medical terms, and aliases live in:

```txt
backend/data/context_vocabulary.json
```

Add organization-specific proper nouns there. The vocabulary is automatically injected into Whisper prompts/hotwords and used by the correction engine.

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

Install FFmpeg if needed:

```bash
brew install ffmpeg
```

## API

```bash
curl -X POST http://127.0.0.1:5001/api/transcribe \
  -F "audio=@sample.webm" \
  -F "language=hi" \
  -F "task=translate"
```

Use `language=en` for English transcription, `language=hi` for Hindi/Hinglish, and `task=translate` for Hindi to English output.

The response includes:

```json
{
  "success": true,
  "text": "cleaned transcript",
  "rawText": "raw whisper output",
  "cleanedText": "cleaned transcript",
  "confidenceScore": 92,
  "audioQualityScore": 95,
  "audioDiagnostics": {},
  "postProcessing": {
    "corrections": ["HbA1c"],
    "entityCorrections": []
  },
  "words": [],
  "confirmations": []
}
```

## Production

```bash
gunicorn "app:create_app()" \
  --bind 127.0.0.1:5001 \
  --workers 1 \
  --threads 4 \
  --timeout 600
```

Large-v3 is slower and memory-heavy. Use GPU settings when available:

```bash
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```
