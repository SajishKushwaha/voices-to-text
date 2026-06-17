# Deployment

This project has two deployable services:

- Frontend: Next.js app from the repository root.
- Backend: Python Flask API from `backend/`, packaged with Docker.

## 1. Deploy Backend on Render

Use `render.yaml` as a Render Blueprint.

Important values:

- Backend health check: `/api/health`
- Dockerfile: `backend/Dockerfile`
- Persistent disk mount: `/app/persistent`
- Model path: `/app/persistent/models/faster-whisper-large-v3`
- SQLite/PDF data path: `/app/persistent/data`

When Render asks for `CORS_ORIGINS`, set it to your frontend domain:

```txt
https://your-frontend.vercel.app
```

For multiple domains, use a comma-separated list:

```txt
https://your-frontend.vercel.app,https://www.yourdomain.com
```

The first backend boot downloads the Faster-Whisper model when `AUTO_DOWNLOAD_MODEL=true`.
With `large-v3`, this is several GB and needs a paid instance plus the persistent disk.
For a lighter deployment, change both values below to `base`, `small`, or `medium`:

```txt
WHISPER_MODEL_SIZE=small
WHISPER_MODEL_PATH=persistent/models/faster-whisper-small
```

After deploy, verify:

```bash
curl https://your-backend.onrender.com/api/health
```

## 2. Deploy Frontend on Vercel

Import the repo into Vercel as a Next.js project from the repository root.

Use these commands/settings:

```txt
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Set frontend environment variables in Vercel:

```txt
NEXT_PUBLIC_BACKEND_API_URL=https://your-backend.onrender.com
NEXT_PUBLIC_TRANSCRIBE_API_URL=https://your-backend.onrender.com/api/transcribe
NEXT_PUBLIC_TRANSCRIBE_WS_URL=wss://your-backend.onrender.com/api/transcribe/stream
NEXT_PUBLIC_MAX_RECORDING_SECONDS=180
NEXT_PUBLIC_STREAM_AUDIO_CHUNK_MS=750
NEXT_PUBLIC_STREAM_RECONNECT_MS=1200
```

Redeploy the frontend after changing any `NEXT_PUBLIC_*` variable.

## 3. Connect Custom Domains

Point your frontend domain to Vercel.
Point your API domain, for example `api.yourdomain.com`, to Render.

Then update:

```txt
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
NEXT_PUBLIC_BACKEND_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_TRANSCRIBE_API_URL=https://api.yourdomain.com/api/transcribe
NEXT_PUBLIC_TRANSCRIBE_WS_URL=wss://api.yourdomain.com/api/transcribe/stream
```

## Notes

- Do not commit `backend/models`, `backend/data`, or `backend/tmp`; they are ignored.
- WebSocket streaming requires `wss://` from the deployed frontend.
- The Next.js `/api/tts` route depends on local Piper files and may need separate production storage/runtime work if TTS is required in production.
