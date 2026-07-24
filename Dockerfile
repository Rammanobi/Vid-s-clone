FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml ./
COPY app/ ./app/
COPY prisma/ ./prisma/

RUN pip install --no-cache-dir .


FROM python:3.12-slim

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000
EXPOSE 8001

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]