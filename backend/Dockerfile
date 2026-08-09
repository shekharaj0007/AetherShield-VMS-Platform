# Slim image for Render free tier (avoids PyTorch OOM on 512MB)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Use slim requirements (no ultralytics/torch/easyocr)
COPY requirements-render.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/sample-data/videos /app/storage/recordings /app/storage/snapshots /app/storage/faces

ENV PYTHONPATH=/app
ENV PROJECT_ROOT=/app
ENV AI_ENABLED=false
ENV AUTO_START_CAMERAS=false
ENV MAX_LIVE_CAMERAS=1
ENV DEFAULT_FPS=5
ENV SKIP_VIDEO_GEN=true

EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
