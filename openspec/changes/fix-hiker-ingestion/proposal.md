## Why

The ingestion layer has never successfully pulled a single reel. It reads every HikerAPI response at the wrong nesting level, calls a `/v1` clips endpoint and `max_id` pagination scheme that does not exist on this API, and maps four metric fields to names the API never returns. Because stage 1 silently yields nothing, every downstream stage — enrichment, analytics, intelligence, knowledge, and the agent — operates on empty or zero-valued data while reporting success.

A separate research project (`insta_ide-imple`) already probed the live API against a real 150k-follower account and saved 4.3 MB of raw responses. That work establishes the true contract; this change makes the code match it.

## What Changes

- **BREAKING** Replace `GET /v1/user/clips/chunk` + `max_id` request pagination with `GET /v2/user/clips` + `page_id`/`next_page_id`. The v1 path was never valid for this API.
- **BREAKING** Replace `GET /v1/media/comments/chunk` with `GET /v2/media/comments`, whose array key is `comments` (not `items`) and whose query parameter is `id` (not `media_id`).
- Add per-endpoint response unwrapping. There is no universal envelope — five distinct shapes exist:
  - `/v2/user/by/username` → payload at `user`
  - `/v2/user/clips` → payload at `response.items[].media` (double-nested)
  - `/v2/media/comments` → payload at `response.comments[]`
  - `/v2/media/info/by/code` → payload at `media_or_ad`
  - `/v1/media/insight` → flat, no wrapper
- Extract `videoUrl` from the `video_versions[]` array instead of a non-existent top-level `video_url` key. Without this, enrichment has nothing to download even once its own defects are fixed.
- Unwrap `caption` from its object form (`caption.text`) — the raw field is always an object, never a bare string.
- **BREAKING** Correct the metric field mapping:
  - `views` ← `play_count` (the `view_count` key is structurally absent from every payload)
  - `shares` ← `reshare_count` (`share_count` does not exist; `media_repost_count` measures a different, much smaller action)
  - `saves` ← `save_count` (confirmed populated, contrary to a stale note in the research project)
- **BREAKING** Drop `reach` from the ingestion contract. It is an owner-only Insights metric this API never returns; leaving it nullable-but-expected makes `metricQuality` permanently `PARTIAL`.
- Redefine `metricQuality` so `FULL` is attainable given what the API actually provides.
- Send `safe_int=true` on all v2 calls and tolerate IDs arriving as either JSON string or number.
- Replace 429/`Retry-After` retry handling with HTTP 402 `InsufficientFunds` detection. No rate limiting was ever observed; credit exhaustion is the real failure mode.
- Derive `Comment.isCreator` by comparing the commenter's `user.pk` against the account owner's `pk`, since `is_created_by_media_owner` is absent (not `false`) on ordinary comments.
- Define `viralityScore` explicitly. The research project has no such formula — it must be designed, not extracted.

## Capabilities

### New Capabilities
- `hiker-ingestion`: fetching Instagram account, reel, metric, and comment data from HikerAPI — endpoint selection, pagination, response unwrapping, field mapping, and error handling.
- `reel-metrics`: deriving engagement, save, share, comment, virality, and view-to-follower figures from ingested counts, including the availability rules that govern `metricQuality`.

### Modified Capabilities
<!-- None. openspec/specs/ is empty; this is the first change in the repo. -->

## Impact

**Code**
- `hiker_ingestion/client.py` — endpoint paths, query parameters, pagination, error classes
- `hiker_ingestion/mapper.py` — every mapping function; `map_metric` most heavily
- `hiker_ingestion/orchestrator.py` — profile unwrapping, `pk` extraction, comment ownership
- `hiker_ingestion/models.py` — `ReelMetricData.reach` removal, `metricQuality` semantics
- `app/metrics.py` — `compute_reel_metrics` duplicates the same derivations and must agree
- `prisma/schema.prisma` — `ReelMetric.reach` column disposition

**Data**
- `videoUrl` values are signed CDN URLs carrying an `oe=` expiry. They must be refreshed by re-fetching the media, not cached long-term. Enrichment must download promptly after ingestion.

**Dependencies**
- None added. `httpx` already covers transport; the research project's use of `curl.exe` is not carried over.

**Not in scope**
- The enrichment download defect, the 768-vs-1536 embedding mismatch, and the missing read APIs are separate changes. This change only guarantees that correct data lands in `Account`, `Reel`, `ReelMetric`, and `Comment`.
