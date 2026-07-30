# ===== Builder Stage =====
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/
COPY prisma/ ./prisma/
COPY hiker_ingestion/ ./hiker_ingestion/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ===== Production Stage =====
FROM python:3.12-slim

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Install runtime deps: curl for health checks, ca-certificates for SSL,
# ffmpeg for audio extraction (both the main Whisper pipeline and Reel Bot's
# media processing shell out to it), libglib2.0-0 (opencv-python-headless
# dynamically links against it even without GUI support - ImportError on
# `import cv2` without it), libgomp1 (faster-whisper's ctranslate2 backend
# needs it for OpenMP threading - "libgomp.so.1: cannot open shared object
# file" without it). None of these surfaced locally because the dev machine
# already had them; only a clean container build exposes the gap.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates ffmpeg libglib2.0-0 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000
EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
