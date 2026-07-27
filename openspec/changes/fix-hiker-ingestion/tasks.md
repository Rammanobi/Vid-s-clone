## 1. Local environment

- [x] 1.1 Install the project so it can actually run: `pip install -e ".[dev]"` — required fixing two pre-existing packaging bugs first: no `[build-system]`/package-discovery config (flat layout with `frontend`/`prisma`/`infra` etc. confused setuptools) and `requires-python = ">=3.12"` pinned against a 3.11.9 interpreter with no 3.12-only syntax anywhere in the code. Both fixed in `pyproject.toml`; install now succeeds.
- [x] 1.2 Suite runs: 466/487 passed on first full baseline. See 9.5 for the complete breakdown and fixes.
- [x] 1.3 Set `HIKER_API_TOKEN` in `.env` — done by the user; verified it loads correctly through `settings.hiker_api_token`

## 2. Client — endpoints, parameters, pagination

- [x] 2.1 Replace `fetch_user_clips` / `fetch_user_clips_all`: use `GET /v2/user/clips` with `user_id`, `page_id`, `safe_int=true`; drop the `/v1/user/clips/chunk` + `max_id` request scheme entirely
- [x] 2.2 Drive pagination from the top-level `next_page_id` cursor; omit `page_id` on the first call; terminate on empty/absent cursor
- [x] 2.3 Replace `fetch_media_comments` / `fetch_media_comments_all`: use `GET /v2/media/comments` with query param `id` (not `media_id`) and `safe_int=true` — comments pagination is intentionally first-page-only (never validated beyond page 1 per the research)
- [x] 2.4 Add `safe_int=true` to `fetch_user_by_username` and every other v2 call
- [x] 2.5 Deleted `fetch_media_info` (`/v1/media/by/id`); `fetch_media_by_code` repointed at `/v2/media/info/by/code`
- [x] 2.6 Deleted the dead `_get_retry_decorator` method

## 3. Client — error handling

- [x] 3.1 Added `HikerInsufficientFundsError` for HTTP 402 with `{"exc_type": "InsufficientFunds"}`; non-retryable
- [x] 3.2 Removed `HikerRateLimitError` and the 429/`Retry-After` path entirely
- [x] 3.3 Kept 401 → `HikerAuthError`, 404 → `HikerNotFoundError`, both non-retryable; `ingest_reels`/`ingest_creator` already wrap per-item work in try/except so one failure doesn't abort the run
- [x] 3.4 `hiker_ingestion/tests/test_client.py` covers 402 (both InsufficientFunds and generic-body cases), 401, 404, confirms none retry, confirms 429 gets no special handling, and confirms genuine transport errors (ConnectError/TimeoutException) still retry — 9/9 passing, verified no real network calls

## 4. Response unwrapping

- [x] 4.1 Added five explicit unwrap helpers in `mapper.py`: `unwrap_user`, `unwrap_clips` (handles the double `items[].media` nesting), `unwrap_comments`, `unwrap_media_info`, `unwrap_insight`
- [x] 4.2 Added `_coerce_id()` — pure `str()`, never routes IDs through `int()`/`float()`
- [x] 4.3 `TestUnwrap` in `hiker_ingestion/tests/test_mapper.py` covers `unwrap_user`, `unwrap_clips` (double-nesting), `unwrap_comments`, `unwrap_media_info`, including empty/missing-key cases

## 5. Mapper — reel and account fields

- [x] 5.1 `map_account` now takes the already-unwrapped `user` object
- [x] 5.2 `map_reel.videoUrl`: selects `max(video_versions, key=bandwidth)`; dead `video_url`/`permalink` fallback deleted
- [x] 5.3 `map_reel.caption`: unwraps `caption.text`, never stringifies the raw object
- [x] 5.4 `map_reel.instagramReelId`: stores the numeric `pk` only
- [x] 5.5 `durationSec`/`postedAt` wired from `video_duration`/`taken_at` (UTC seconds)
- [x] 5.6 Added `is_reel()` predicate (`product_type=="clips"` and `media_type==2`); orchestrator now skips non-Reels before mapping

## 6. Mapper — metrics

- [x] 6.1 `views` ← `play_count`; `view_count` lookup deleted
- [x] 6.2 `shares` ← `reshare_count`, not `share_count`/`media_repost_count`
- [x] 6.3 `saves` ← `save_count`
- [x] 6.4 `reach` removed from `ReelMetricData` and from the mapping
- [x] 6.5 `engagement_rate` now divides by views, not `follower_count`
- [x] 6.6 `viralityScore = engagementRate*0.5 + shareRate*0.3 + viewToFollower*0.2` as named constants — **note:** this replaced a conflicting recency-discounted formula an earlier design draft proposed; the design doc has been corrected to match (a persisted column can't depend on wall-clock time)
- [x] 6.7 `metricQuality`: FULL/PARTIAL based on views/likes/commentsCount/saves/shares only
- [x] 6.8 Verified zero-guarded — self-check asserts `views=0, followers=0` → all rates `0`, no exception

## 7. Orchestrator

- [x] 7.1 `ingest_creator` now fetches the profile once, unwraps once, and passes the unwrapped `user` through — the old code called `fetch_user_by_username` twice and read `pk` off the raw root both times, which is why `instagram_id` was always empty
- [x] 7.2 **Bug found and fixed beyond the original task scope:** `map_comment` was reading the comment's own `pk` (the comment's id) as the author id, not `user.pk`. Verified against raw payload: comment `pk=18209380177352304` vs actual author `user.pk=47831239820` — confirmed on all 32 sampled comments. `isCreator` would never have been true. Fixed to compare `user.pk` (or top-level `user_id`) against the owner id.
- [x] 7.3 **Design correction:** the design doc claimed the composite `"{pk}_{owner_pk}"` id is only used by `/v1/media/insight` and would never be constructed. The recorded call log (`hikerapi_calls` entries 5/9/13/17/21) proves `/v2/media/comments` also requires the composite form. The orchestrator now builds `f"{media_pk}_{instagram_id}"` (or uses `clip["id"]` directly, since it's already that composite) before calling `ingest_comments`. `design.md` corrected in place with the evidence.

## 8. Schema and cross-module consistency

- [x] 8.1 Confirmed against the live Neon DB: `Account`, `Reel`, `ReelMetric`, `Comment`, `CreatorProfile` all 0 rows — design's zero-row assumption holds, `reach` column drop required no backfill
- [x] 8.2 Dropped `ReelMetric.reach` from `prisma/schema.prisma` and from `hiker_ingestion/db.py`'s upsert SQL (found and fixed — not in either agent's assigned file scope, would have broken the insert with a column-count mismatch)
- [x] 8.3 Reconciled — `app/metrics.py::compute_virality_score` now uses the same `VIRALITY_*` named constants and formula as `hiker_ingestion/mapper.py`; verified by reading both side by side
- [x] (found) `app/analytics.py:148` called `db.insert_reel_snapshot(..., reach=reel.get("reach"))` — `insert_reel_snapshot`'s signature no longer accepts `reach` (already fixed in `app/db.py`), so this was a live `TypeError` waiting to fire on every snapshot job run. Removed the stale argument.
- [x] 8.4 Not applicable — no Hiker-related variable name changed (`HIKER_API_TOKEN`/`HIKER_BASE_URL` untouched)

## 9. Verification

- [x] 9.1 `test_full_metrics_matches_worked_example` (metrics: play_count/save_count/reshare_count) + `TestMapReel::test_full_data` (video_duration=39.75, taken_at=1784462647) — both pytest-collected, both pass
- [x] 9.2 Added `test_play_count_already_equals_ig_plus_fb_so_views_is_unaffected_by_either` — the mapper never reads `ig_play_count`/`fb_play_count` directly (by design, `play_count` already equals their sum per the research), so this guards that `views` comes from `play_count` regardless, and that a `None` `fb_play_count` (no FB cross-post) is not mistaken for zero engagement
- [x] 9.3 **Live call made with explicit user approval**, against `okaashish`, `max_reels=2, max_comments=50`. Actual calls: 1 profile + 1 clips page + 2 comments = 4 Hiker API calls total, exactly as estimated. This is the only live-API activity in the entire change; every other verification used saved/mocked data.
- [x] 9.4 Verified directly against the live DB: 1 Account row (real follower count, grown from research's 150,165 to 153,958), 2 Reel rows (real signed CDN `videoUrl`s, real UTF-8 captions with curly quotes intact, real durations/timestamps), 2 ReelMetric rows (real engagement/virality figures), 23 Comment rows. `videoUrl` confirmed to be a genuine `cdninstagram.com` signed URL with an `oe=` expiry param, matching the design's prediction exactly.
- [x] 9.5 Full run: 466 passed / 21 failed (58.77s). 13 of the 21 were stale tests broken by this change's own deliberate rewrites (viralityScore signature, dropped `reach`, corrected zero-views floor) — all fixed, verified 170/170 passing across every touched test file. The remaining 8 are `AttributeError: module 'langchain' has no attribute 'debug'` — a pre-existing `langchain`/`langgraph` version conflict unrelated to this change, deferred to a separate LangChain-migration change. Two files/tests excluded from the run entirely for an unrelated reason: `test_transcription.py` and one WebSocket test both trigger a native crash (`0xc0000139`) via `app/transcription/vad.py` loading a speech model at import time — flagged, not fixed, out of scope here.

## 11. Bugs found only by the live run (not visible to any mocked test)

- [x] 11.1 **`Account.id` (and all 13 tables' `id` columns) had no database-level default.** `@default(uuid())` in Prisma is client-side only — it never materialized as a Postgres `DEFAULT`, so raw SQL inserts (which every hand-written query in this codebase uses, bypassing Prisma Client) got `NULL` and violated the not-null constraint. Fixed with `ALTER TABLE ... ALTER COLUMN id SET DEFAULT gen_random_uuid()::text` across all 13 tables.
- [x] 11.2 **`updatedAt` had the same gap**, across the 7 tables that have it (`Account`, `CompetitorInsight`, `ContentIntelligence`, `CreatorProfile`, `Reel`, `ReelMetric`, `Session`). Fixed with a `DEFAULT CURRENT_TIMESTAMP` plus a `BEFORE UPDATE` trigger per table, so it also auto-refreshes on update — matching what `@updatedAt` is supposed to mean, not just satisfying the not-null constraint on insert.
- [x] 11.3 **Timezone mismatch**: every timestamp column in the schema is `timestamp without time zone`, but `_safe_timestamp()` produced tz-aware UTC datetimes. asyncpg refuses to encode a tz-aware value against a naive column. Fixed by stripping `tzinfo` after the UTC conversion (the value is still correctly UTC, just unlabeled, matching the schema-wide convention). Updated the two test/self-check assertions that expected the old tz-aware value.
- [x] 11.4 **A bug introduced during this change's own implementation**: `ingest_reels()` was called with `max_comments=max_comments` (added when wiring up the composite comment id, task 7.3) but never declared `max_comments` as one of its own parameters — a `NameError` on every reel, silently swallowed by the per-reel `try/except`, so comments were dropped with no visible error until the live run's log was inspected line by line. Fixed the signature and threaded the parameter through from `ingest_creator`.

None of these four were catchable by the 219 tests run so far, because none of them exercise a real Postgres connection — every one is invisible to a mocked `DatabaseClient`. This is the concrete argument for why task 9.3 (the live call) was worth doing rather than deferring indefinitely.

## 10. Documentation

- [x] 10.1 `docs/api.md`'s Ingestion section replaced the fictitious batch `POST /ingest` with the four routes that actually exist in `app/routes/ingest.py`
- [x] 10.2 `docs/pipelines.md` now notes `videoUrl` is a signed CDN URL (`oe=` hex expiry) and must be downloaded promptly, not cached
- [x] 10.3 `docs/pipelines.md` documents `views`←`play_count`/`shares`←`reshare_count` and that reach/impressions/watch-time are structurally unavailable; also found and fixed `docs/database.md` still listing `reach: Int?` on both `ReelMetric` and `ReelSnapshot` after the column was dropped from the real schema
