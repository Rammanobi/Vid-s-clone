# Hybrid Retrieval & Search

## Architecture

```
User Query
    │
    ├──► Dense Path: CLIP embedding → pgvector cosine similarity (HNSW)
    │
    └──► Sparse Path: tsquery → tsvector BM25 (GIN index, weighted: A/B/C)
               │
               └──► Metadata filters: topic, time_range, content_format, hook_type
                           │
                           ▼
              ┌─────────────────────┐
              │ Fuse & Dedup        │
              │ (avg dense+sparse)  │
              └─────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │ Reranker            │
              │ (term coverage +    │
              │  fused score)       │
              └─────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │ Top-K Selection     │
              │ (default 10)        │
              └─────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │ Confidence Scoring  │
              │ (max retrieval * 0.35│
              │ + max rerank * 0.40 │
              │ + coverage * 0.25)  │
              └─────────────────────┘
```

## Dense Retrieval (pgvector)

**Method**: Cosine similarity on 1536-d embeddings with HNSW index.

```python
async def search_reels_dense(self, query_embedding: list[float], metadata_filters, limit=20):
    query_vec = normalize_embedding(query_embedding)
    # SQL:
    # 1 - (r."combinedEmbedding" <=> $1::vector) AS retrieval_score
    # ORDER BY r."combinedEmbedding" <=> $1::vector ASC
```

- Normalization: L2 unit vector
- Index: HNSW with `vector_cosine_ops`
- Returns: `reel_id, retrieval_score, contexts, topic, hook_text, content_format, hook_type, caption, duration_sec`

## Sparse Retrieval (BM25)

**Method**: PostgreSQL `tsvector` with `plainto_tsquery` + `ts_rank`.

```sql
-- search vector is auto-synced via trigger:
new."searchVector" :=
  setweight(to_tsvector('english', coalesce(new.caption, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(new.transcript, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(new."visualSummary", '')), 'C');
```

- Weights: caption (A) > transcript (B) > visual_summary (C)
- Index: GIN on `Reel.searchVector`
- Returns: `reel_id, bm25_score, matched_terms, topic, hook_text, ...`

## Metadata Filters

Built dynamically via `_build_metadata_clause()`:

| Filter | SQL | Notes |
|--------|-----|-------|
| `account_id` | `r."accountId" = $N` | Exact match |
| `time_range` | `r."postedAt" >= NOW() - INTERVAL '$N days'` | Supports `"last_7_days"`, `"last_30_days"`, etc. |
| `topic` | `ci."topic" ILIKE $N` | Case-insensitive, requires ContentIntelligence JOIN |
| `content_format` | `ci."contentFormat" = $N::"ContentFormat"` | Enum exact match, requires CI JOIN |
| `hook_type` | `ci."hookType" = $N::"HookType"` | Enum exact match, requires CI JOIN |

## Hybrid Fusion

```python
def _fuse_scores(retrieval_score, bm25_score) -> float:
    scores = []
    if retrieval_score > 0: scores.append(retrieval_score)
    if bm25_score > 0: scores.append(bm25_score)
    return sum(scores) / len(scores) if scores else 0.0
```

## Reranking

Lightweight term-matching reranker (`app/reranker.py`):

```python
reranker_score = (
    term_coverage * 0.4 +
    fused_score   * 0.3 +
    retrieval     * 0.2 +
    bm25          * 0.1
)
```

## Confidence Scoring

```python
combined_score = (
    max_retrieval_score  * 0.35 +
    max_reranker_score   * 0.40 +
    query_term_coverage  * 0.25
)
```

Used by the LangGraph agent to decide routing:
- `≥ 0.8`: Full reasoner + recommendations
- `≥ 0.5`: Clarification question appended
- `< 0.5`: Decline to answer

## Fallback Behavior

When pgvector/tsvector queries fail (e.g., missing embeddings), the hybrid search falls back to simple term frequency matching:

```python
# Count query term matches in caption + transcript + topic + hook_text
# Weight: exact match = 1.0, prefix match = 0.5
# Sort by score, return top 5
```
