# API Reference

Base URL: `http://localhost:8000` (dev) / `https://api.vidsclone.com` (prod)

## Authentication

### POST /auth/token

Issue a JWT. Protected routes require `Authorization: Bearer <token>`.

```
Request:
  x-www-form-urlencoded:
    username: admin
    password: <plaintext>

Response 200:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Password hashing**: PBKDF2-SHA256 with 16-byte random salt, 100,000 iterations. Generate with:

```python
from app.auth import hash_password
hash_password("your-password")   # returns "salt:hexhash"
```

Set `ADMIN_PASSWORD_HASH` env var to the output.

### GET /auth/verify

Verify a token is still valid.

```
Headers: Authorization: Bearer <token>
Response 200: { "sub": "admin", "exp": 1712345678 }
```

## Health

### GET /health

```
Response 200:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}

Response 503 (degraded):
{
  "status": "degraded",
  "database": "unavailable",
  "redis": "unavailable",
  "version": "1.0.0"
}
```

## Sessions

All session endpoints require `Authorization: Bearer <token>`.

### POST /sessions

Create a new chat session.

```
Response 201:
{
  "id": "uuid",
  "userId": "admin",
  "createdAt": "2025-01-01T00:00:00Z",
  "updatedAt": "2025-01-01T00:00:00Z"
}
```

### GET /sessions

List sessions for the authenticated user. Cached 120s.

```
Query: ?limit=20
Response 200:
{
  "sessions": [{ "id": "uuid", "userId": "admin", "summary": null, "createdAt": "...", "updatedAt": "..." }],
  "count": 1
}
```

### GET /sessions/{session_id}

Get a single session. Cached 300s.

```
Response 200:
{
  "id": "uuid",
  "userId": "admin",
  "summary": null,
  "createdAt": "...",
  "updatedAt": "..."
}
```

### PUT /sessions/{session_id}/summary

Update session summary. Invalidates cache.

```
Request body: summary (string, plain text in body)
Response 200: { "status": "ok", "session": { ... } }
```

### POST /sessions/{session_id}/messages

Add a chat message.

```
Request body: role (string), content (string), citations (JSON array, optional)
Response 200: { "status": "ok", "message": { "id": "uuid", ... } }
```

### GET /sessions/{session_id}/messages

Get chat history.

```
Query: ?limit=100
Response 200: { "messages": [...], "count": 5 }
```

## Agent

### POST /agent/chat

Invoke the LangGraph agent synchronously.

```
Request:
{
  "session_id": "uuid",
  "message": "What topics perform best for my audience?"
}

Response 200:
{
  "session_id": "uuid",
  "response": "Based on analysis of 47 reels...",
  "citations": [
    { "source": "creator_profile", "type": "creator_knowledge", "summary": "Best topics: [fitness, nutrition]" }
  ],
  "confidence_score": 0.85,
  "intent": { "intent_type": "content_strategy", "topic": "fitness" },
  "evidence": { "source": "llm_reasoner", "context_used": ["creator_profile", "analytics"] },
  "elapsed_sec": 3.42
}
```

### POST /agent/chat/stream

Server-Sent Events (SSE) streaming version.

```
Request: same body as /agent/chat
Response: text/event-stream

data: {"event": "start", "session_id": "uuid"}

data: {"event": "complete", "session_id": "uuid", "response": "...", "citations": [...], "confidence_score": 0.85, ...}
```

### GET /agent/graph

Get the compiled LangGraph topology.

```
Response 200:
{
  "nodes": ["conversation_memory", "query_understanding", ...],
  "edges": [
    {"source": "conversation_memory", "target": "query_understanding", "conditional": false},
    ...
  ]
}
```

### WebSocket /agent/ws

Real-time bidirectional chat. Requires token in each message.

```
Client → Server:
{
  "session_id": "uuid",
  "message": "What topics perform best?",
  "token": "eyJhbGci..."
}

Server → Client:
{
  "event": "start",
  "session_id": "uuid"
}

Server → Client:
{
  "event": "complete",
  "session_id": "uuid",
  "response": "...",
  "citations": [...],
  "confidence_score": 0.85,
  "intent": {...},
  "evidence": {...}
}

Server → Client (error):
{
  "event": "error",
  "detail": "Failed to process message"
}
```

## Ingestion

### POST /ingest

Trigger ingestion for specific usernames.

```
Request:
{
  "usernames": ["user1", "user2"],
  "max_reels": 50,
  "max_comments": 200
}

Response 200:
{
  "status": "completed",
  "results": {
    "user1": { "reels_ingested": 15, "comments_ingested": 120 },
    "user2": { "reels_ingested": 22, "comments_ingested": 180 }
  }
}
```

### GET /ingest/status

Get current ingestion status.

## Pipeline

### POST /pipeline/run

Trigger a pipeline run for specified stages.

```
Request:
{
  "stages": ["ingestion", "enrichment", "analytics", "intelligence", "knowledge"],
  "enrichment_limit": 10,
  "analytics_limit": 100,
  "intelligence_limit": 100,
  "intelligence_use_llm": true
}

Response 200:
{
  "pipeline_run_id": "uuid",
  "status": "success",
  "stages": [
    { "stage": "ingestion", "status": "success", "elapsed_sec": 5.2, "details": { "ingested_accounts": ["user1"], "total": 1 } },
    { "stage": "enrichment", "status": "success", "elapsed_sec": 12.1, "details": { "enriched_count": 10 } },
    { "stage": "analytics", "status": "success", "elapsed_sec": 3.0, "details": { "analytics_processed": 100, "snapshots_created": 100 } },
    { "stage": "intelligence", "status": "success", "elapsed_sec": 15.4, "details": { "processed": 100, "failed": 0 } },
    { "stage": "knowledge", "status": "success", "elapsed_sec": 2.1, "details": { "reels_analyzed": 200, "profile_updated": true } }
  ],
  "elapsed_sec": 37.8
}
```

### GET /pipeline/status

Get current pipeline status info.

## Content

### GET /content/reels

List reels with full intelligence.

```
Query: ?limit=100&offset=0
Response 200: { "reels": [...], "count": 100 }
```

### GET /content/reels/{id}

Get single reel with metrics, intelligence, and snapshots.

### GET /content/reels/{id}/snapshots

Get metric drift snapshots for a reel.

```
Query: ?limit=30&offset=0
```

## Analytics

### GET /analytics/summary

Aggregated analytics summary.

```
Response 200:
{
  "total_reels": 150,
  "total_accounts": 5,
  "avg_engagement_rate": 3.45,
  "avg_virality_score": 0.0234,
  "total_views": 2500000,
  "total_likes": 85000
}
```

## Creator

### GET /creator/profile

Get the creator intelligence profile.

```
Response 200:
{
  "account_id": "default",
  "patterns": {
    "best_topics": ["fitness", "nutrition", "workout"],
    "worst_topics": ["technology"],
    "best_hook_types": ["CURIOSITY", "PROBLEM_SOLUTION"],
    "best_posting_day": "Wednesday",
    "best_duration_range": "30-60s",
    "best_content_format": "TUTORIAL",
    "audience_interests": ["weight loss", "meal prep", "home gym"]
  },
  "competitor_trends": { ... }
}
```

### POST /creator/refresh

Force refresh of creator intelligence.

## Knowledge

### GET /knowledge/search

Hybrid search across reels.

```
Query: ?query=fitness+tips&topic=fitness&limit=10
Response 200:
{
  "query": "fitness tips",
  "results": [
    {
      "reel_id": "uuid",
      "retrieval_score": 0.89,
      "contexts": ["caption text...", "transcript text..."],
      "topic": "fitness",
      "hook_text": "you won't believe this quick workout",
      "content_format": "TUTORIAL",
      "hook_type": "CURIOSITY",
      "caption": "...",
      "duration_sec": 45.2
    }
  ],
  "count": 10
}
```

## Metrics

Prometheus metrics are available at `GET /metrics` on port **8001** (separate from the main API port).

```
GET http://localhost:8001/metrics
```

See [Grafana dashboards](monitoring-security.md) for pre-built visualization panels.
