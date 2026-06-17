FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    FLASK_ENV=production \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=10000 \
    DATABASE_PATH=persistent/data/medical_ai.db \
    PDF_UPLOAD_DIR=persistent/data/pdfs \
    STREAM_DIR=persistent/tmp/streams \
    UPLOAD_DIR=persistent/tmp/uploads \
    WHISPER_MODEL_PATH=persistent/models/faster-whisper-large-v3

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      ffmpeg \
      libgomp1 \
      poppler-utils \
      tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY data/context_vocabulary.json ./data/context_vocabulary.json
COPY scripts ./scripts
COPY run.py .
COPY start.sh .

RUN chmod +x /app/start.sh \
    && mkdir -p /app/persistent/data/pdfs /app/persistent/tmp/uploads /app/persistent/tmp/streams /app/persistent/models

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["/app/start.sh"]
