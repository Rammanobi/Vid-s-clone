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

# Install runtime deps: curl for health checks, ca-certificates for SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
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
