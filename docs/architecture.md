# Architecture Overview

## Three-Layer Intelligence Stack

The system ingests Instagram Reels data and progressively builds intelligence across three vertical layers:

```
┌──────────────────────────────────────────────────┐
│                 Layer 3: Creator Knowledge        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ Creator  │  │Competitor│  │  Trend Store     ││
│  │ Profile  │  │Insights  │  │  (topics, hooks) ││
│  └──────────┘  └──────────┘  └──────────────────┘│
├──────────────────────────────────────────────────┤
│                 Layer 2: Content Intelligence      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │  Topic   │  │Hook Type │  │Content Format    ││
│  │  CTA     │  │Sentiment │  │Teaching/Narrative││
│  └──────────┘  └──────────┘  └──────────────────┘│
├──────────────────────────────────────────────────┤
│                 Layer 1: Analytics                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │Engagement│  │Virality  │  │Metric Snapshots  ││
│  │ Rates    │  │ Scores   │  │ (drift tracking) ││
│  └──────────┘  └──────────┘  └──────────────────┘│
├──────────────────────────────────────────────────┤
│              Foundation: Data Ingestion           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ Hiker API│  │  Reels   │  │   Enrichment     ││
│  │Client    │  │Storage   │  │(Whisper/OCR/CLIP)││
│  └──────────┘  └──────────┘  └──────────────────┘│
└──────────────────────────────────────────────────┘
```

## Phase Map

| Phase | Purpose | Key Components |
|-------|---------|---------------|
| 1 | Ingestion | Hiker API → Account/Reel/Comment DB tables |
| 2 | Enrichment | Whisper (speech), OCR (text), CLIP (visual embeddings) |
| 3 | Analytics | Engagement rate, virality score, metric snapshots, drift detection |
| 4 | Content Intelligence | LLM + rule-based topic/hook/format/sentiment extraction |
| 5 | Creator Knowledge | Pattern mining, competitor integration, trend analysis, creator profiling |
| 6 | AI Agent | LangGraph orchestrated retrieval-augmented conversation |
| 7 | Hybrid Retrieval | pgvector (dense) + tsvector (sparse) + metadata filters + reranking |
| 8 | Integration & Testing | Offline/online pipeline orchestration, monitoring |
| 9 | UX & Deployment | Next.js frontend, Docker, CI/CD, scaling |

## Data Flow

```
Hiker API ──→ Ingestion ──→ DB: Account, Reel, Comment
                                    │
                                    ▼
                              Enrichment (Whisper/OCR/CLIP)
                                    │
                          ┌─────────┴──────────┐
                          ▼                     ▼
                    Analytics Layer      Content Intelligence
                    (metrics, rates,     (topic, hook, format,
                     snapshots)          sentiment, CTA)
                          │                     │
                          └──────────┬──────────┘
                                     ▼
                              Creator Knowledge
                          (patterns, competitor,
                           trends, profile)
                                     │
                                     ▼
                    ┌─── LangGraph Agent ─────────────────┐
                    │  Query → Retrieve → Rerank →        │
                    │  Confidence → Reason → Recommend    │
                    │  → Cite → Memory Update             │
                    └─────────────────────────────────────┘
```

## LangGraph Orchestration

The AI agent uses a `StateGraph` with 13 nodes, 2 conditional routing decision points, and 6 sequential edges:

```
[Conversation Memory] → [Query Understanding] → [Query Transformation]
    → [Retrieval Planner] → [Parallel Retrieval] → [Reranker]
    → [Context Fusion] → [Confidence Evaluation]
        │
        ├── confidence ≥ 0.8 → [Conversational Reasoner]
        │                           │
        │                           ├── confidence ≥ 0.8 → [Recommendation Generator]
        │                           └── confidence < 0.8 → [Citation Builder]
        ├── 0.5 ≤ confidence < 0.8 → [Set Clarification]
        └── confidence < 0.5 → [Set Decline]
                                        │
                                        ▼
                              [Citation Builder] → [Memory Update] → END
```

## Service Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  FastAPI │────▶│  Redis   │     │PostgreSQL│
│  :8000   │     │  :6379   │     │  :5432   │
│  :8001   │     └──────────┘     └──────────┘
│(metrics) │           │               │
└──────────┘           │               │
     │                 │               │
     ▼                 ▼               ▼
┌──────────────────────────────────────────┐
│             Monitoring Stack              │
│  Prometheus (:9090) → Grafana (:3001)    │
│  node_exporter (:9100)                   │
│  cadvisor (:8080)                        │
└──────────────────────────────────────────┘
```

## Key Architectural Decisions

1. **Pooled asyncpg connections**: `DatabaseClient` uses `asyncpg.create_pool()` with configurable min/max size (defaults 2/20), query limit (50k), and connection lifetime (3600s). Neon-optimized via `?pooled=true` hint.

2. **Redis caching layer**: `CacheClient` (via `redis.asyncio`) with cache-aside pattern, JSON serialization, configurable TTL, and null-safe fallback. Cached: sessions (300s), session lists (120s).

3. **Hybrid retrieval**: Combines dense (pgvector cosine similarity with HNSW index) and sparse (PostgreSQL tsvector BM25 with GIN index) search. Results fused via score averaging, reranked by a cross-encoder-style term matcher.

4. **Dual intelligence extraction**: Rule-based (`app/intelligence.py`) for fast, no-cost analysis; LLM-based (`app/llm_intelligence.py`) for deeper understanding. Results merged with LLM preferred on non-null fields.

5. **Offline + online pipelines**: `PipelineStage` enum sequences 7 stages; scheduler runs them on intervals. Agent graph runs per-user query in real-time.
