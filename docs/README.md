# Vid's Clone — Developer Documentation

> AI-powered content strategy intelligence for Instagram Reels.

## Table of Contents

1. [Architecture Overview](architecture.md)
2. [Database Schema](database.md)
3. [API Reference](api.md)
4. [Pipelines](pipelines.md)
5. [AI/ML Modules](ai-ml.md)
6. [Retrieval & Search](retrieval.md)
7. [LangGraph Agent](langgraph.md)
8. [Frontend](frontend.md)
9. [Deployment & Scaling](deployment.md)
10. [Monitoring & Security](monitoring-security.md)
11. [Testing](testing.md)
12. [JSON Examples](examples.md)

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Set up database
createdb vids_clone
psql vids_clone < prisma/neon-init.sql

# Run migrations (Prisma)
npx prisma generate
npx prisma db push

# Start API server
uvicorn app.main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Project Structure

```
├── app/                    # FastAPI backend
│   ├── graph/             # LangGraph agent (nodes, state, registry, tools)
│   ├── routes/            # API endpoints
│   ├── clip/              # CLIP visual feature extraction
│   ├── ocr/               # OCR text overlay extraction
│   ├── transcription/     # Whisper speech-to-text
│   ├── cache.py           # Redis caching layer
│   ├── pool.py            # DB connection pool config
│   ├── main.py            # App factory + lifespan
│   └── ...
├── frontend/               # Next.js + Tailwind CSS
├── prisma/                 # Prisma schema + Neon init SQL
├── hiker_ingestion/        # Hiker API ingestion client
├── infra/                  # Docker, K8s, env configs
│   ├── docker/
│   └── k8s/
├── prometheus/             # Prometheus config + alerts
├── grafana/                # Grafana dashboards + datasource
├── .github/workflows/      # CI/CD pipelines
└── tests/                  # Load tests
```

## Key Technologies

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Python 3.12 |
| Database | PostgreSQL 17 + pgvector |
| ORM / Schema | Prisma |
| AI Agent | LangGraph |
| Embeddings | CLIP (openai/clip-vit-base-patch32) |
| Speech | Whisper (openai/whisper-tiny) |
| OCR | EasyOCR |
| LLM | OpenAI / OpenAI-compatible |
| Frontend | Next.js 15 + Tailwind CSS |
| Cache | Redis 7 |
| Monitoring | Prometheus + Grafana |
| Container | Docker + Docker Compose |
| Orchestration | Kubernetes (optional) |
| CI/CD | GitHub Actions |
