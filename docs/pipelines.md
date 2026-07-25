# Pipeline Workflows

The system runs two kinds of pipelines: **offline batch jobs** and **online LangGraph orchestration** triggered per user query.

## Offline Pipeline Stages

Sequenced via `PipelineStage` enum in `app/pipeline.py`:

| # | Stage | Function | What It Does |
|---|-------|----------|-------------|
| 1 | `INGESTION` | `run_ingestion_stage` | Fetches creator data from Hiker API → stores Account, Reel, Comment records |
| 2 | `ENRICHMENT` | `run_enrichment_stage` | Downloads video, runs Whisper (speech→text), EasyOCR (text overlays), CLIP (visual embeddings) → updates Reel |
| 3 | `ANALYTICS` | `run_analytics_stage` | Computes engagement/virality/save/share/comment rates → upserts ReelMetric + inserts ReelSnapshot |
| 4 | `INTELLIGENCE` | `run_intelligence_stage` | Extracts topic, hook type, CTA, content format, sentiment (rule-based + optional LLM) → upserts ContentIntelligence |
| 5 | `KNOWLEDGE` | `run_knowledge_stage` | Pattern mining, competitor/trend integration, creator profile update → upserts CreatorProfile, CompetitorInsight, TrendStore |
| 6 | `AGENT` | `run_agent_stage` | Validates the compiled LangGraph is operational |
| 7 | `RETRIEVAL` | `run_retrieval_stage` | Validates merge/dedup/rerank/confidence pipeline |

### Stage Runner Registry (`STAGE_RUNNERS`)

```python
STAGE_RUNNERS = {
    PipelineStage.INGESTION: run_ingestion_stage,
    PipelineStage.ENRICHMENT: run_enrichment_stage,
    PipelineStage.ANALYTICS: run_analytics_stage,
    PipelineStage.INTELLIGENCE: run_intelligence_stage,
    PipelineStage.KNOWLEDGE: run_knowledge_stage,
    PipelineStage.AGENT: run_agent_stage,
    PipelineStage.RETRIEVAL: run_retrieval_stage,
}
```

### Full Pipeline Orchestration

`app/pipeline.py::run_pipeline()` accepts optional stage list, runs them sequentially, and records Prometheus metrics for each stage:

```
PipelineResult
├── pipeline_run_id: str (UUID)
├── status: "success" | "partial" | "failed"
├── stages: list[StageResult]
│   ├── stage: PipelineStage
│   ├── status: "success" | "skipped" | "failed"
│   ├── elapsed_sec: float
│   ├── details: dict | None
│   └── error: str | None
└── elapsed_sec: float
```

### Prometheus Metrics Recorded

- `pipeline_runs_total{status}` — counter
- `pipeline_run_duration_seconds{status}` — histogram
- `pipeline_stage_duration_seconds{stage, status}` — histogram
- `pipeline_stage_errors_total{stage}` — counter
- `pipeline_stage_status{stage, status}` — gauge (1=success)
- `pipeline_last_run_timestamp{status}` — gauge
- `pipeline_last_run_duration_seconds{status}` — gauge

## Ingestion Stage Detail

Uses the `hiker_ingestion/` package:

```
HikerClient (httpx, rate-limited) → IngestionOrchestrator
  → ingest_creator(username, max_reels, max_comments)
    → get_user_info → upsert Account
    → get_user_reels → upsert Reel
    → get_reel_comments → upsert Comment
```

Rate-limited to avoid Hiker API throttling. Skips on API errors (logged, not fatal).

## Enrichment Stage Detail

`app/enrichment.py::enrich_reel()`

```
1. Download video via httpx
2. Select modalities:
   - Extract audio → VAD speech_score → if >0.1 run Whisper
   - Sample frames → EasyOCR text_score → if >0.15 run OCR
   - Sample frames → frame_diff visual_change_score → if >0.05 run CLIP
3. Run selected modalities in parallel:
   - Whisper: returns transcript + transcriptJson
   - EasyOCR: returns text_overlays list
   - CLIP: returns embedding (1536-d vector) + visual_topics + visual_summary
4. Update Reel row with enrichment results
5. Extract rule-based intelligence (fast path, no LLM needed)
```

## Intelligence Stage Detail

Dual extraction (see `llm_intelligence.py::extract_intelligence_hybrid()`):

```
1. Rule-based extraction (free, instant):
   - topic: visual_topics + text frequency
   - hook_type: regex patterns
   - cta: regex patterns
   - content_format: keyword matching
   - teaching_style: heuristic
   - narrative_style: heuristic
   - audience_intent: keyword matching
   - sentiment: positive/negative/neutral word counts
   - visual_style: visual_topics mapping

2. LLM extraction (if use_llm=True):
   - System prompt defines JSON schema
   - Input: transcript (3k chars) + caption (1k chars) + overlays + visual topics + summary
   - Output JSON parsed into ContentIntelligenceSchema

3. Merge: LLM result preferred for non-null fields, else rule-based fallback
```

### Input Availability Check

```python
def get_input_availability(...) -> dict[str, bool]:
    # Returns which inputs are present
    # If < 2 inputs, flagged as "partial" → LLM warned
```

## Scheduler Background Loops

`app/scheduler.py` runs two infinite loops as asyncio tasks, started during app lifespan:

### Creator Update Loop

```
while True:
    run_creator_intelligence_pipeline(db, limit=200)
    sleep(CREATOR_UPDATE_INTERVAL_HOURS * 3600)
```

Updates: pattern analysis, competitor insights, trend store, creator profile.

### Pipeline Update Loop

```
while True:
    try:
        run_pipeline(db, stages=[ENRICHMENT, ANALYTICS, INTELLIGENCE])
    except Exception:
        consecutive_failures += 1
    sleep(3600)  # 1 hour
```

Both loops have Prometheus gauges for running status and consecutive failures. On shutdown, tasks are cancelled gracefully.

## Error Handling & Fallbacks

| Failure Scenario | Behavior |
|-----------------|----------|
| Hiker API down | Ingestion stage → skipped, next cycle retries |
| Video download fails | Enrichment → skipped for that reel |
| Whisper/OCR/CLIP model fails | Individual modality skipped |
| LLM API error | Intelligence falls back to rule-based, retries with backoff |
| DB connection error | Pool returns exception → AppException → 503 |
| Graph node fails | Agent returns error message, logs failure |
| Redis unavailable | Cache operates in null-safe mode (no-op, no crash) |
