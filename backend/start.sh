#!/bin/sh
set -eu

: "${PORT:=10000}"
: "${AUTO_DOWNLOAD_MODEL:=true}"

mkdir -p \
  "$(dirname "${DATABASE_PATH:-persistent/data/medical_ai.db}")" \
  "${PDF_UPLOAD_DIR:-persistent/data/pdfs}" \
  "${STREAM_DIR:-persistent/tmp/streams}" \
  "${UPLOAD_DIR:-persistent/tmp/uploads}" \
  "${WHISPER_MODEL_PATH:-persistent/models/faster-whisper-large-v3}"

if [ "${AUTO_DOWNLOAD_MODEL}" = "true" ] && [ ! -f "${WHISPER_MODEL_PATH}/model.bin" ]; then
  python scripts/download_model.py
fi

exec gunicorn "app:create_app()" \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --threads "${WEB_THREADS:-4}" \
  --timeout "${WEB_TIMEOUT:-600}" \
  --worker-class gthread
