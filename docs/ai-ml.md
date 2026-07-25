# AI/ML Modules

## Whisper (Speech-to-Text)

**File**: `app/transcription/`

### Architecture

```
Video URL → download → extract audio (ffmpeg) → VAD (silero) → Whisper (tiny)
```

### Components

| Module | Responsibility |
|--------|-------------|
| `vad.py` | Voice Activity Detection via silero VAD model. Returns `speech_score` (0.0–1.0). Threshold: 0.1 |
| `whisper.py` | Wraps `openai/whisper-tiny` via `faster-whisper`. Returns segments with timestamps and per-word details |
| `processor.py` | Orchestrates audio extraction → VAD → Whisper. Returns `(transcript: str, transcriptJson: list[dict])` |
| `media.py` | Downloads video bytes and extracts audio waveform via `pydub`/`ffmpeg` |
| `models.py` | `TranscriptionSegment` dataclass: start, end, text, words, confidence |

### Output Schema

```python
# transcriptJson structure
[
  {
    "start": 0.5,        # seconds
    "end": 2.3,
    "text": "you won't believe this",
    "words": [
      {"start": 0.5, "end": 0.9, "text": "you", "probability": 0.95},
      {"start": 0.9, "end": 1.2, "text": "won't", "probability": 0.98},
    ]
  }
]
```

### Performance

- `whisper-tiny`: ~2× real-time on CPU, ~10× on GPU
- VAD pre-filtering: skips 40% of reels with no speech (saves compute)

## OCR (Text Overlay Extraction)

**File**: `app/ocr/`

### Architecture

```
Video → frame sampling (1fps) → EasyOCR → text dedup → text_overlays[]
```

### Components

| Module | Responsibility |
|--------|-------------|
| `extractor.py` | Samples frames from video, runs EasyOCR per frame, deduplicates overlapping detections |
| `processor.py` | Orchestrates: download → sample → OCR → merge |
| `media.py` | Video frame extraction via OpenCV |

### Frame Sampling Strategy

- Rate: 1 frame per second of video
- Max: 60 frames per video
- Each frame: resize to max dimension 1280px (keeps aspect ratio)

### Text Dedup (IOU-based)

```python
# Overlapping bounding boxes merged via Intersection-over-Union > 0.5
# Text strings deduplicated via Levenshtein ratio > 0.8
```

### Output

```python
# text_overlays: list[str]
["Swipe up for free guide", "5-minute abs routine", "Link in bio"]
```

## CLIP (Visual Feature Extraction)

**File**: `app/clip/`

### Architecture

```
Video → frame sampling → CLIP model (openai/clip-vit-base-patch32)
  → embedding (512-d) + zero-shot classification → visual_topics + visual_summary
```

### Components

| Module | Responsibility |
|--------|-------------|
| `extractor.py` | Runs CLIP model on sampled frames, returns pooled embedding, classified topics via zero-shot labels, generated summary |
| `models.py` | `VisualFeatures` dataclass: embedding, topics, summary |
| `processor.py` | Orchestrates sample → CLIP → normalize → return |

### Embedding Pipeline

1. Sample up to 10 evenly-spaced frames from video
2. Run each frame through CLIP ViT encoder → 512-d vector
3. Mean-pool frame embeddings → single 512-d embedding
4. Normalize to unit length (L2)
5. Zero-shot classify against 40 predefined topic labels
6. Top-5 topics selected
7. Summary generated: concatenation of top-3 topic labels

### Zero-Shot Topic Labels

```python
TOPIC_CANDIDATES = [
    "fitness and workout", "nutrition and diet", "cooking and recipes",
    "technology and gadgets", "gaming", "travel and adventure",
    "fashion and style", "beauty and makeup", "personal finance",
    "entrepreneurship", "career advice", "education and learning",
    "parenting and family", "relationships and dating",
    "mental health", "motivation and inspiration", "comedy and humor",
    "music and dance", "art and design", "photography",
    "nature and wildlife", "pets and animals", "DIY and crafts",
    "home improvement", "automotive", "sports and athletics",
    "outdoor activities", "meditation and mindfulness",
    "productivity and organization", "book reviews and literature",
    "science and technology", "history and culture", "news and politics",
    "social media tips", "business and marketing", "investing and trading",
    "real estate", "legal advice", "health and wellness",
    "language learning",
]
```

### pgvector Storage

The 512-d CLIP embedding is projected to 1536-d by the model's projection head and stored in `Reel.combinedEmbedding` (`vector(1536)`). Indexed via HNSW for approximate nearest neighbor search:

```sql
CREATE INDEX reel_embedding_hnsw_idx
ON "Reel" USING hnsw ("combinedEmbedding" vector_cosine_ops);
```

## LLM Integration

**File**: `app/llm.py` — `LLMClient`

### Features

- Wraps any OpenAI-compatible API (configurable `base_url`)
- Retry with exponential backoff on 429/5xx/timeout (configurable `max_retries`)
- Prometheus metrics: `llm_requests_total{provider, model, status}`, `llm_request_duration_seconds{provider}`
- Structured output via `response_format={"type": "json_object"}`
- `extract_structured()` convenience method: system + user prompt → parsed JSON

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | — | API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL for OpenAI-compatible API |
| `LLM_MODEL` | `gpt-4o-mini` | Model identifier |
| `LLM_MAX_RETRIES` | 3 | Retry count on transient failures |
| `LLM_TIMEOUT_SEC` | 30 | Request timeout in seconds |

### Prompts

- **Intent Extraction**: `INTENT_EXTRACTION_SYSTEM_PROMPT` — Extracts `intent_type`, `topic`, `metric`, `time_range`, `comparison_type` from user query
- **Query Rewrite**: `QUERY_REWRITE_SYSTEM_PROMPT` — Optimizes user query for search
- **Reasoner**: `REASONER_SYSTEM_PROMPT` — Evidence-based answer generation
- **Recommendation**: `RECOMMENDATION_SYSTEM_PROMPT` — Actionable content strategy recommendations
- **Content Intelligence**: `_SYSTEM_PROMPT` (in `llm_intelligence.py`) — Structured content analysis

## Cross-Encoder Reranker

**File**: `app/reranker.py`

Not a neural cross-encoder, but a lightweight term-matching reranker:

```
1. merge_and_dedup_candidates(): Fuse dense + sparse scores, dedup by reel_id
2. rerank_candidates(): Score each candidate by:
   - term_coverage: % of query terms present in text (weight 0.4)
   - fused_score: avg dense+sparse score (weight 0.3)
   - retrieval_score: max dense score (weight 0.2)
   - bm25_score: max sparse score (weight 0.1)
3. select_top_k(): Return top-k (default 10)
4. compute_retrieval_confidence(): Combined = max_retrieval*0.35 + max_reranker*0.40 + query_term_coverage*0.25
```
