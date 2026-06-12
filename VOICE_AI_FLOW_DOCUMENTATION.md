# Local Voice AI Flow Documentation

Ye document is project ka complete flow explain karta hai: kaise Next.js frontend audio record karta hai, Flask backend audio receive karta hai, Faster-Whisper locally transcription karta hai, aur result chat UI me show hota hai. Isme ye bhi covered hai ki project me kya-kya changes kiye gaye aur kyu.

## 1. Project Goal

Goal tha ek completely free, self-hosted Voice-to-Text system banana:

```txt
User Voice
  -> Next.js records audio
  -> Flask receives audio
  -> Faster-Whisper transcribes locally
  -> Text returns to Next.js
  -> Chat interface me transcription show hoti hai
```

Paid APIs use nahi kiye gaye:

```txt
OpenAI API: no
Deepgram: no
AssemblyAI: no
Murf: no
```

Sab local/self-hosted hai.

## 2. Main Tech Stack

Frontend:

```txt
Next.js App Router
TypeScript
Tailwind CSS
MediaRecorder API
React hooks/components
```

Backend:

```txt
Flask
Flask-CORS
Faster-Whisper
FFmpeg
Python virtual environment
```

Local AI Model:

```txt
Faster-Whisper tiny
Device: cpu
Compute type: int8
Languages: English + Hindi
```

## 3. Current Running Services

Next.js frontend:

```txt
http://localhost:3000
```

Flask backend:

```txt
http://127.0.0.1:5001
```

Main API:

```txt
POST http://127.0.0.1:5001/api/transcribe
```

## 4. Folder Structure

Important files/folders:

```txt
app/page.tsx
components/voice/
hooks/useVoiceRecorder.ts
lib/transcription/
types/transcription.ts

backend/app/config.py
backend/app/routes/transcribe.py
backend/app/services/transcription_service.py
backend/app/utils/files.py
backend/scripts/download_model.py
backend/.env
backend/models/faster-whisper-tiny
```

Piper TTS files bhi project me hain:

```txt
app/api/tts/route.ts
lib/tts/
voices/
public/generated/tts/
```

## 5. Frontend Flow

Frontend ka main page:

```txt
app/page.tsx
```

Ye page `VoiceChat` component render karta hai:

```tsx
<VoiceChat />
```

Main UI component:

```txt
components/voice/VoiceChat.tsx
```

Isme WhatsApp-style chat layout hai:

```txt
Header
Chat message area
Recorder control footer
```

## 6. Recording Flow

Recording ka logic reusable hook me hai:

```txt
hooks/useVoiceRecorder.ts
```

Ye browser ke `MediaRecorder API` ka use karta hai.

Supported actions:

```txt
Start Recording
Pause Recording
Resume Recording
Stop Recording
Reset
```

Flow:

```txt
User clicks Start Recording
  -> Browser microphone permission ask karta hai
  -> getUserMedia audio stream deta hai
  -> MediaRecorder chunks collect karta hai
  -> Timer start hota hai
  -> Waveform animation active hoti hai
```

Stop par:

```txt
MediaRecorder stop hota hai
  -> Audio Blob create hota hai
  -> Blob chat message me attach hota hai
  -> Audio automatically Flask API ko upload hota hai
  -> Recorder timer reset ho jata hai
```

## 7. Frontend API Upload Flow

API client:

```txt
lib/transcription/api.ts
```

Function:

```ts
transcribeAudio(audioBlob)
```

Ye audio ko `FormData` me bhejta hai:

```txt
field name: audio
request type: multipart/form-data
```

Frontend environment:

```env
NEXT_PUBLIC_TRANSCRIBE_API_URL=http://127.0.0.1:5001/api/transcribe
NEXT_PUBLIC_MAX_RECORDING_SECONDS=180
```

## 8. Chat UI Flow

Jab recording complete hoti hai:

```txt
VoiceChat.tsx
  -> new message create hota hai
  -> status: transcribing
  -> audio player bubble me show hota hai
  -> loading text show hota hai
```

API success par:

```txt
status: ready
text: transcribed text
language: detected/fallback language
processingTime: backend processing time
```

API failure par:

```txt
status: error
Retry button show hota hai
```

Chat bubble component:

```txt
components/voice/TranscriptionBubble.tsx
```

## 9. Backend Flask Flow

Flask app entry:

```txt
backend/run.py
```

App factory:

```txt
backend/app/__init__.py
```

Transcription route:

```txt
backend/app/routes/transcribe.py
```

Endpoint:

```txt
POST /api/transcribe
```

Backend receives:

```txt
multipart/form-data
audio file field: audio
```

## 10. Backend Validation

Backend checks:

```txt
audio field present hai ya nahi
filename valid hai ya nahi
file type allowed hai ya nahi
file size limit ke andar hai ya nahi
```

Allowed extensions:

```txt
.webm
.ogg
.wav
.mp3
.m4a
.mp4
.mpeg
```

Allowed MIME types:

```txt
audio/*
video/webm
video/mp4
application/octet-stream
```

Validation file:

```txt
backend/app/utils/files.py
```

## 11. Temporary File Handling

Uploaded audio temporary folder me save hota hai:

```txt
backend/tmp/uploads
```

Processing complete hone ke baad file delete hoti hai:

```python
finally:
    delete_file_quietly(temp_path)
```

Isse server storage fill nahi hota.

## 12. Faster-Whisper Integration

Main transcription service:

```txt
backend/app/services/transcription_service.py
```

Model load hota hai:

```python
self._model = WhisperModel(
    model_source,
    device=settings.device,
    compute_type=settings.compute_type,
)
```

Current config:

```env
WHISPER_MODEL_SIZE=tiny
WHISPER_MODEL_PATH=models/faster-whisper-tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Actual model path:

```txt
/Users/sajishkumar/Desktop/plasma it/peeper/backend/models/faster-whisper-tiny
```

## 13. Why Model Changed

Pehle model `small` tha:

```env
WHISPER_MODEL_SIZE=small
```

Phir speed ke liye `base` kiya gaya:

```env
WHISPER_MODEL_SIZE=base
```

User ne bataya:

```txt
bara sentence jada time laa raha hai convert karna ma
```

Isliye latency reduce karne ke liye model `tiny` kar diya:

```env
WHISPER_MODEL_SIZE=tiny
```

Result:

```txt
small model size: approx 464 MB
base model size: approx 141 MB
tiny model size: approx 75 MB
```

Speed test sample:

```txt
base: around 1.35s
tiny: around 0.70s
```

Tradeoff:

```txt
tiny = fastest, accuracy thodi kam
base/small = slower, accuracy better
```

## 14. Model Download

Model downloader:

```txt
backend/scripts/download_model.py
```

Command:

```bash
cd backend
. .venv/bin/activate
python scripts/download_model.py
```

Ye model Hugging Face se download karta hai:

```txt
Systran/faster-whisper-tiny
```

Download ke baad runtime request ke time internet ki zarurat nahi hoti.

## 15. Language Detection Issue and Fix

Problem:

Short/noisy audio clips me Faster-Whisper kabhi-kabhi English/Hindi ko galat detect kar raha tha, example:

```txt
Detected language 'bn' is not enabled for this service.
```

Pehle backend unsupported language par error return karta tha.

Fix:

```env
WHISPER_RETRY_UNSUPPORTED_LANGUAGE=true
WHISPER_FALLBACK_LANGUAGE=en
```

Ab flow:

```txt
Auto-detect language
  -> Agar language en/hi nahi hai
  -> Fallback language en se retry
  -> Chat bubble me transcription show
```

Response me extra metadata added:

```json
{
  "detectedLanguage": "bn",
  "languageFallbackUsed": true,
  "language": "en"
}
```

Frontend bubble me small note show hota hai:

```txt
Auto-detected BN, retried as EN.
```

## 16. Flask Response Format

Success response:

```json
{
  "success": true,
  "text": "Transcribed speech",
  "language": "en",
  "detectedLanguage": "en",
  "languageFallbackUsed": false,
  "processingTime": 0.7,
  "duration": 1.55,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.0,
      "text": "Transcribed speech"
    }
  ]
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

## 17. Error Handling

Frontend handles:

```txt
Microphone permission denied
Browser recording unsupported
Recording error
Upload/transcription failure
Retry transcription
```

Backend handles:

```txt
Missing audio
Invalid filename
Unsupported file type
File too large
Missing local model
Transcription exception
```

## 18. Security Changes

Security measures:

```txt
No paid/external transcription API
Multipart file validation
Allowed extensions only
Allowed MIME types only
Max upload size
Temporary file cleanup
CORS restricted to frontend origin
No shell command execution for user audio
Local model path required in production
```

## 19. Important Commands

Install frontend:

```bash
npm install
```

Run frontend:

```bash
npm run dev
```

Setup backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/download_model.py
python run.py
```

Run both:

```bash
npm run dev:all
```

Build frontend:

```bash
npm run build
```

Typecheck:

```bash
npm run typecheck
```

Python compile check:

```bash
backend/.venv/bin/python -m compileall backend/app backend/scripts
```

Test Flask health:

```bash
curl http://127.0.0.1:5001/api/health
```

Test transcription:

```bash
curl -X POST http://127.0.0.1:5001/api/transcribe \
  -F "audio=@sample.wav;type=audio/wav"
```

## 20. Production Deployment Notes

Frontend:

```bash
npm run build
npm run start
```

Backend:

```bash
cd backend
. .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:5001 --workers 1 --threads 4 --timeout 180
```

Production suggestions:

```txt
Use Nginx reverse proxy
Keep Flask private/internal
Set exact CORS_ORIGINS
Pre-download model during deployment
Install ffmpeg on server
Use GPU if available for faster long audio
Use tiny for speed, base/small for better accuracy
```

## 21. What Was Fixed During Development

Fixes/changes made:

```txt
404 page issue fixed by rendering VoiceChat on app/page.tsx
Tailwind CSS added
Recorder UI created
MediaRecorder hook created
Flask backend added
Faster-Whisper integrated
FFmpeg installed
Model downloader added
Local model path enforced
small -> base -> tiny model switch for speed
Unsupported bn language detection issue fixed with fallback retry
Recorder timer reset after upload
Retry button added for failed transcriptions
Response typing added in TypeScript
Validation and cleanup added in Flask
```

## 22. Final Current State

Current active model:

```txt
Faster-Whisper tiny
CPU
int8
English + Hindi
Fallback language: English
```

Current active backend:

```txt
http://127.0.0.1:5001
```

Current active frontend:

```txt
http://localhost:3000
```

The system is now ready for local voice recording and transcription without any paid API.
