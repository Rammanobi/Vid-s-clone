## Context

`hiker_ingestion/` talks to HikerAPI to populate `Account`, `Reel`, `ReelMetric`, and `Comment`. It has never
worked: `client.py` calls `/v1/user/clips/chunk` (`fetch_user_clips`, L170-178) and
`/v1/media/comments/chunk` (`fetch_media_comments`, L198-206), neither of which exists on this API surface —
the research project's exhaustive grep of every successful call it ever made found zero references to either
path (`research-endpoints.md` §1). Because `_raise_for_status` (client.py L62-76) turns a 404 into
`HikerNotFoundError`, and `ingest_reels` (orchestrator.py L76-78) does not wrap the initial
`fetch_user_clips_all` call in a `try/except`, that error propagates uncaught through `ingest_creator` into
`main()`'s bare per-username loop (orchestrator.py L216-221, no `try/except`) — so a real run against this
code would raise before a single `Reel` row is written, for the very first username in `HIKER_USERNAMES`.

`app/metrics.py` (`compute_reel_metrics`, L184-273) independently re-derives the same rates from raw counts
that `hiker_ingestion/mapper.py` (`map_metric`, L132-197) already computed once at ingestion time. The two
must agree on formulas, or a reel's stored `ReelMetric` row and a live re-computation in `app/` will disagree
silently.

This document specifies exactly how the corrected client, mapper, orchestrator, and models fit together, and
resolves the nine decisions called out for this change. It reproduces the verified contract from
`research-endpoints.md` and `research-metrics.md` (both already reviewed) rather than re-deriving it.

## Goals / Non-Goals

**Goals:**
- Specify the exact unwrap path, endpoint, and query parameters for every HikerAPI call the ingestion layer
  makes, matching the verified contract in `research-endpoints.md` §2-3.
- Resolve the `instagramReelId` / `videoUrl` / `safe_int` ambiguities with a single, DB-schema-consistent
  answer for each.
- Define `viralityScore` and settle the `reach`/`metricQuality`/engagement-denominator questions so
  `hiker_ingestion/mapper.py` and `app/metrics.py` compute identical numbers from identical inputs.
- Define the exception hierarchy and retry policy around the one confirmed failure mode (HTTP 402).
- State what happens to `prisma/schema.prisma` and to any rows already written by the current code.

**Non-Goals:**
- Fixing the enrichment download step, the 768-vs-1536 embedding mismatch, or adding read APIs — all called
  out as separate changes in `proposal.md`'s "Not in scope".
- Adding comment/likers pagination — `research-endpoints.md` §4 explicitly flags comments pagination as
  unverified beyond page 1, and likers as never paginated; this change fetches first-page-only, matching what
  was actually validated.
- Introducing any new HTTP client dependency — `httpx` stays, `tenacity` is removed (see Decision 8).

## Decisions

### 1. Envelope unwrapping strategy — explicit per-endpoint functions, not one generic helper

There is no universal envelope. `research-endpoints.md` §3 documents five distinct shapes for the six
endpoints this change touches:

| Endpoint | Payload path |
|---|---|
| `/v2/user/by/username` | `/user` (flat object) |
| `/v2/user/clips` | `/response/items[]`, each element's real media object at `/response/items/N/media` (double-nested) |
| `/v2/media/comments` | `/response/comments[]` (flat elements, key is `comments` not `items`) |
| `/v2/media/info/by/code` | `/media_or_ad` (flat object) |
| `/v1/media/insight` | root (no wrapper at all) |
| `/v2/media/likers` | `/users[]` (flat array, no `response` wrapper, unlike clips/medias/comments) |

**Decision:** write one small unwrap function per endpoint (`_unwrap_user`, `_unwrap_clips`,
`_unwrap_comments`, `_unwrap_media_by_code`, `_unwrap_insight`), each hard-coding its one known path, living in
`client.py` next to the fetch method that calls it. Each returns the shape the corresponding `mapper.py`
function expects (a flat dict, or a flat list of dicts) — `_unwrap_clips` in particular must reach two levels
deep (`response.items[i].media`) and return the list of `media` dicts, not the wrapper items.

**Alternative considered:** the research project's own fallback-chain helper —
`response.get("response", response).get("items") or .get("comments") or .get("users") or .get("likers")`
(`research-endpoints.md` §3, "the scripts' own `unwrap_items()`"). Rejected: it works for the research
scripts because they never need to tell one endpoint's absence-of-data apart from another's, but it silently
masks a shape change (e.g. a future endpoint returning an empty `items` list is indistinguishable from one
returning no `response` key at all) and it cannot express the double-nesting of clips (`items[].media`)
without a second, endpoint-specific unwrap step layered on top anyway — at which point the "generic" helper
is only handling half the problem and the endpoint-specific code is mandatory regardless. Explicit functions
are the same amount of code, are individually testable against the fixture responses in
`research-endpoints.md` §5, and fail loudly (`KeyError`/`None`) at the exact point a shape assumption breaks
instead of falling through to the next `or` clause.

### 2. `instagramReelId` — store numeric `pk`; do not call `/v1/media/insight` in the default flow

Three identifiers exist: numeric `pk` (`"3944679501543145356"`), shortcode `code` (`"Da-URtaPn-M"`), and the
composite `"{pk}_{owner_pk}"`.

> **Corrected during implementation.** An earlier draft of this decision claimed the composite id's only
> consumer was `/v1/media/insight` and that it would therefore never be constructed. That is wrong. The
> recorded call log in `okaashish_last5_reels_data.json` (`hikerapi_calls.calls`, entries 5/9/13/17/21) shows
> **`/v2/media/comments` is called with `id` set to the composite form**, e.g.
> `{'id': '3944679501543145356_45093317380', 'safe_int': True}` — and `/v2/media/likers` likewise. The raw
> payload confirms `media.id` *is* the composite (verified `media.id == f"{media.pk}_{owner_pk}"` on every
> sampled reel). The composite must therefore be constructed for comment ingestion. The spec's scenario for
> the comments endpoint was correct; this decision was not.

**Decision:**
- `Reel.instagramReelId` (schema.prisma L92, `@unique String`) stores the raw numeric `pk`, matching
  `research-metrics.md` §A's row for `Reel.instagramReelId` and requiring no schema change.
- `code` is **not** persisted as a new column. It is read off the clips/media-info response and used only
  within the same request/response cycle (e.g. if `/v2/media/info/by/code` is ever called for a refresh, the
  caller must already have `code` in hand from the clips listing that produced the reel).
- **This change does not call `/v1/media/insight` at all.** `research-endpoints.md` §5 and
  `research-metrics.md` §B/F show `/v1/media/insight` returning `save_count: null` even for this
  non-owned-but-public test account, and its example response (§5) does not carry `reshare_count` — i.e. it
  cannot supply two of the four fields this change needs, while `/v2/user/clips` and
  `/v2/media/info/by/code` supply all four (`like_count`, `comment_count`, `play_count`, `save_count`,
  `reshare_count`) with zero observed nulls (`research-metrics.md` §F).
- The composite id **is** constructed, but only at the comment-fetching call site, as
  `f"{reel.instagram_reel_id}_{account.instagram_id}"`. Both operands are already stored, so it stays a pure
  derivation and is never persisted as its own column. It is passed to `/v2/media/comments` as `id`.

**Alternative considered:** persist `code` as a new nullable `Reel.code` column so any later job can call
`/v2/media/info/by/code` without re-listing clips. Rejected for this change: `proposal.md`'s Impact section
scopes `prisma/schema.prisma` changes to "`ReelMetric.reach` column disposition" only; adding a column is a
schema change the proposal did not ask for. Noted as an Open Question below rather than done silently.

### 3. `safe_int=true` type tolerance

`research-endpoints.md` §2 confirms (as inferred, not documented by HikerAPI): with `safe_int=true`, IDs that
would overflow a JS safe integer come back as JSON strings (e.g. 19-digit media `pk`), while smaller IDs
(e.g. 11-digit user `pk`) come back as native JSON numbers, in the same response.

**Decision:** one coercion helper, `_coerce_id(value: str | int) -> str`, used everywhere an ID-like field
(`pk`, `id`, `user_id`, `owner pk`) is read, defined as `str(value)` — never routed through `_safe_int`/
`_safe_float` (which call `int()`/`float()` and exist for genuine numeric metrics, not identifiers). `str()`
on a Python `int` is exact regardless of digit count (Python ints are arbitrary precision, and `json`
deserializes a bare integer literal to a Python `int`, not a `float`, so there is no 53-bit float rounding
risk even for the 19-digit case if it ever arrived as a JSON number instead of a string). All four fetch
methods send `safe_int=true` as a query parameter on every v2 call, per `research-endpoints.md` §2 — including
`fetch_user_by_username`, `fetch_user_clips`, `fetch_media_by_code`, and `fetch_media_comments`, none of which
send it today (`client.py`'s URL strings are built without any `safe_int` param at all, e.g. L166, L173,
L201, L236).

**Alternative considered:** use `_safe_int_optional` (already in `mapper.py` L28-34) for IDs too, since it
already returns `int | None`. Rejected: the DB schema stores `instagramReelId`, `authorId`, and
`Account.instagramId` as `String` (schema.prisma L92, L198, and the Account model), so the value must become
a `str` at some point regardless — going through `int()` first only reintroduces the precision question this
decision exists to close, for zero benefit.

### 4. `videoUrl` selection — pick the highest-bandwidth rendition, not index 0

`video_versions[]` has 2-3 renditions (`research-metrics.md` §C). The research scripts (`video_url()` in
`hikerapi_last5_dashboard.py` L133-137, `extract_video()` in `hikerapi_dashboard.py` L123-124) blindly take
`video_versions[0]`. In the one sample checked, all entries happened to share identical width/height/bandwidth
(720×1280), so index-0 worked, but §C is explicit that "the code makes no explicit 'pick highest bandwidth'
logic" and a genuinely multi-resolution response would silently take whichever rendition is listed first.

**Decision:** select `max(video_versions, key=lambda v: v.get("bandwidth", 0))`. This is one line more than
`[0]`, costs nothing when all renditions tie (same result as index-0 in every sample actually observed), and
is correct if HikerAPI ever returns genuinely different resolutions in a different order. Reject "keep index
0": it has no verified guarantee about ordering (the research files never state renditions are bandwidth-sorted)
and picking the *smallest*/wrong rendition on some future response would be a silent quality regression with
no error to catch it.

**Signed-URL freshness — what the ingestion contract promises:** the CDN URL carries an `oe=` hex-encoded
expiry (confirmed in §C: `oe=6A63A43B` decodes to a Unix timestamp "several days out" from `taken_at`). The
object's own `url_expiration_timestamp_us` field is unpopulated (always `null`), so there is no in-band,
structured expiry to store. **The ingestion contract promises only this:** `videoUrl` is valid *as of the
moment this ingestion run fetched it* and is not guaranteed valid at any later read. Ingestion does not parse
`oe=` into a stored expiry column (no such column exists on `Reel`, and adding one is out of scope per the
proposal's Impact list). Enrichment (out of scope for this change, per `proposal.md` Not-in-scope) is
responsible for downloading promptly after ingestion, or re-fetching via `fetch_media_by_code` if it lapses —
this is stated in `proposal.md`'s Impact/Data section already and this design does not weaken it.

### 5. `reach` removal and `metricQuality` redefinition

`reach` is confirmed absent from every sampled payload across all three research runs
(`research-metrics.md` §B, §F) — not null-but-present, structurally never returned by any endpoint this
change calls.

**Decision:** drop `ReelMetric.reach` from `prisma/schema.prisma` (currently L157, `reach Int?`) and from
`hiker_ingestion/models.py`'s `ReelMetricData` (L65) and `mapper.py`'s `map_metric` (L146-148, L179 — the
`reach` term in the `is_partial` check). **Reject "keep nullable and never populate":** the whole reason this
needs deciding is that `mapper.py`'s current `is_partial = any(x is None for x in [saves, shares, reach])`
(L178-180) makes `metricQuality` permanently `PARTIAL`, because `reach` is unconditionally `None` — exactly
the bug `proposal.md`'s "Why" section calls out. Keeping the column nullable-and-unpopulated preserves that
bug in schema form: every future reader has to independently learn "this column is always null, ignore it,"
instead of the schema simply not offering a promise it can't keep. Migration cost is a plain `DROP COLUMN`
(see Decision 9 — no rows exist with real data in it to lose).

`ReelSnapshot.reach` (schema.prisma L186) has the same problem but is outside `proposal.md`'s stated Impact
list (which names only `ReelMetric.reach`); flagged as an Open Question rather than changed here.

**`metricQuality` redefined in terms of what IS obtainable:** `FULL` = `saves` and `shares` are both
non-null; `PARTIAL` = either is null. Per `research-metrics.md` §F, `save_count`/`reshare_count` are non-null
in 100% of the `/v2/user/clips` and `/v2/media/info/by/code` samples (20+12+12 reels checked, zero nulls) — so
under the corrected mapping, `FULL` is the expected steady-state outcome, not a permanently-unreachable
target as today. `PARTIAL` remains reachable in principle (e.g. a future media type or account state that
does null one of these) without ever being forced by a field this API structurally never returns.

### 6. `viralityScore` formula — designed fresh, not extracted

`research-metrics.md` §A/E confirms no such formula exists anywhere in the source research project (zero
grep hits for "virality"/"viral_score" in any `.py`/`.json`/`.html` file). It must be designed here.

**Inputs available, all already mapped elsewhere in this change:** `plays` (views), `likes`, `comments`,
`saves`, `reshares` (shares), `follower_count`, `duration_sec`, and age-since-posted (derivable from
`posted_at`).

**Decision — a deterministic, zero-guarded weighted composite of the three rates already computed above:**

```
virality_score = round(
    engagement_rate * 0.5 + share_rate * 0.3 + view_to_follower * 0.2,
    4,
)
```

This is the formula specified in `specs/reel-metrics/spec.md` ("Virality score formula"). Design and spec
agree; the spec is authoritative.

Reasoning:
- **Reuses already-guarded inputs.** `engagement_rate`, `share_rate` and `view_to_follower` are each
  independently zero-guarded by earlier requirements, so `virality_score` inherits those guards and needs no
  division of its own. No path can raise `ZeroDivisionError`.
- **Captures spread beyond the follower base.** The `view_to_follower` term (weight 0.2) is exactly the
  reach-vs-audience-size ratio the research project computes as `plays_per_follower`
  (`research-metrics.md` §E). A reel that breaks out to Explore/FYP scores higher than one that only reached
  its existing followers, which is the intuitive meaning of "virality".
- **Shares weighted above generic engagement.** `share_rate` carries its own 0.3 weight *in addition* to
  already being inside `engagement_rate`'s numerator, so a reel that spreads by sharing outranks one with
  equal engagement concentrated in likes.
- **Deterministic — no wall-clock input.** `viralityScore` is a *persisted* column on `ReelMetric`. Any term
  derived from `now` would make the same reel produce a different score on every recompute, so the stored
  value would encode when the pipeline last ran rather than what the data says, and no test could assert a
  fixed expected value without freezing the clock. Time-based drift is already modelled properly by
  `ReelSnapshot`, which captures point-in-time counts on a schedule — recency belongs there, not baked into
  a stored scalar.
- **`duration_sec` deliberately excluded**: no research evidence ties duration to virality (no
  watch-time/retention data exists at all per `research-metrics.md` §E). Including it would be invention
  layered on invention. It stays on `ReelData` for other consumers (e.g. content intelligence).

**Alternatives considered:**
- *A recency-discounted composite* — weighted engagement density times a `1/(1+age_hours/168)` half-life
  term. Rejected for the determinism reason above: it makes a persisted column depend on wall-clock time.
  Recorded as an Open Question for a future *ranking* use-case, where a decayed score computed at query
  time (not stored) would be appropriate.
- *Reuse `app/metrics.py`'s existing ad hoc `compute_virality_score`* (L88-106, median of per-view ratios of
  likes/comments/saves/shares). Rejected: no reach-vs-follower term at all — a reel with 10 followers and 10
  plays could score identically to one with 10M followers and 10M plays, contradicting "virality" as spread
  beyond your base.
- *`mapper.py`'s current formula* (L170-172:
  `(engagement_rate + (share_rate or 0) * 2) / 10 + 1.0`). Rejected: derived from `engagement_rate`, whose
  denominator Decision 7 changes, so its output would silently shift underneath it; its `+ 1.0` floor and
  arbitrary `/10` scaling are unexplained in the current code.
- *A percentile/z-score against the account's own historical reels.* Rejected for this change: requires a
  second query (the account's prior `ReelMetric` rows) and a defined baseline window — a data dependency
  `map_metric` does not have (it receives one reel's raw response, not the account's history). Noted as an
  Open Question.

**Worked example** (matching the spec scenario): `engagement_rate=4.0253`, `share_rate=0.6232`,
`view_to_follower=7.9080` → `4.0253*0.5 + 0.6232*0.3 + 7.9080*0.2 = 3.7812`.

### 7. Denominator consistency — plays wins for all rate metrics except plays-per-follower

Two disagreements exist in the current code, not one:

1. `research-metrics.md` §E is unambiguous and already internally consistent: `engagementRate`, `likeRate`,
   `commentRate`, `saveRate`, `shareRate` all divide by **plays** (`work/hikerapi_last5_dashboard.py`
   L230-234); only `plays_per_follower` divides by **followers** (L235).
2. `app/metrics.py` **already matches this** — `compute_engagement_rate` (L46-58), `compute_save_rate`
   (L61-67), `compute_share_rate` (L70-76), and `compute_comment_rate` (L79-85) all divide by their `views`
   parameter; only `compute_view_to_follower` (L109-112) divides by `follower_count`. This file does not need
   to change its denominators.
3. `hiker_ingestion/mapper.py`'s `map_metric` is the one place that actually disagrees with both:
   `engagement_rate` divides by `follower_count` (L150-156) while, three lines later in the same function,
   `save_rate` and `share_rate` divide by `views` (L158-164) and `comment_rate` divides by `views` (L166-168).
   That is, `map_metric` is internally inconsistent with itself, and its `engagement_rate` term disagrees
   with `app/metrics.py`'s `compute_engagement_rate` for the same inputs.

**Decision:** `map_metric`'s `engagement_rate` is corrected to divide by `views` (plays), matching its own
`save_rate`/`share_rate`/`comment_rate` lines and matching `app/metrics.py` exactly:
`engagement_rate = (likes + comments + (saves or 0) + (shares or 0)) / views * 100 if views > 0 else 0.0`.
`view_to_follower` (L174-176, already `views / follower_count`) is unchanged — it is the one ratio that is
supposed to divide by followers, and it already does, in both files.

No alternative was seriously considered here: `app/metrics.py` and the verified research formulas already
agree with each other; the only outlier is `mapper.py`'s `engagement_rate` line, so it is the one that moves.

### 8. Error handling — 402 `InsufficientFunds` is the real failure mode; delete the dead retry method

`research-endpoints.md` §6: zero evidence of 429/`Retry-After` handling anywhere in the research project; the
only confirmed error-body shape is HTTP 402 with `{"exc_type": "InsufficientFunds", ...}`. No HikerAPI rate
limit number is documented or discoverable anywhere in that project — treat it as unknown, not zero.

**Exception hierarchy (`client.py`):**
```
HikerAPIError                       (base, unchanged)
├── HikerAuthError                  (401 — unchanged)
├── HikerNotFoundError              (404 — unchanged)
├── HikerInsufficientFundsError     (NEW — 402, or a 200/4xx body containing "exc_type": "InsufficientFunds")
└── (generic HikerAPIError)         (any other non-2xx — unchanged catch-all via httpx.HTTPStatusError)
```
`HikerRateLimitError` (client.py L24-25) and its 429 branch in `_raise_for_status` (L71-75) are deleted —
`research-endpoints.md` §6 found no evidence this API sends 429 at all, so keeping bespoke handling for it is
speculative code for a failure mode never observed, per the same file's own conclusion ("no numeric HikerAPI
rate limit... is stated or discoverable anywhere in this project").

**Retry policy:** `HikerInsufficientFundsError` is **not retried** — it means the API key's credits are
exhausted, which more attempts cannot fix and which will be true for every subsequent call on that same key
regardless of which Instagram account is being processed. It propagates all the way out of `_request` through
`main()`'s per-username loop (orchestrator.py L216-221) and aborts the whole batch, not just the current
username — retrying or continuing to the next username would only burn more of a budget that is already at
zero. `HikerAuthError`/`HikerNotFoundError` remain non-retried, deterministic failures (unchanged from
today). The existing manual exponential-backoff loop in `_request` (client.py L93-159) is kept for
`httpx.TimeoutException`/`httpx.ConnectError` only — `HikerRateLimitError` is removed from its retry tuple
(L115) since that class no longer exists.

**The dead `_get_retry_decorator` (client.py L78-91):** it references `retry`, `stop_after_attempt`,
`wait_exponential`, `retry_if_exception_type`, and `before_sleep_log` — none of which are imported anywhere in
`client.py` (confirmed: the file's only imports are `asyncio`, `time`, `typing.Any`, and `httpx`), and nothing
in the codebase calls this method. **Decision: delete it outright.** The manual backoff loop already
implemented in `_request` covers the one retryable case; there is no reason to also carry a second, broken,
unused retry mechanism. `tenacity>=9.0,<10` (`hiker_ingestion/requirements.txt` L3) is removed from the
dependency list as part of the same cleanup — it is declared but never imported, so it is a phantom
dependency, not a partially-used one.

**Alternative considered:** actually wire up `tenacity` properly instead of deleting the dead method, since
it's a more standard retry primitive. Rejected: `proposal.md`'s Impact/Dependencies section states "None
added" and explicitly contrasts this change with the research project's ad hoc tooling; the hand-rolled loop
in `_request` already works for the one exception pair that needs retrying, so adopting a new library for
that is unnecessary churn for a fix-focused change.

### 9. Backward compatibility / migration

**What's actually in the database today, and why:** `fetch_user_clips` (client.py L170-178) calls
`/v1/user/clips/chunk`, a path `research-endpoints.md` §1 confirms was never exercised anywhere in the
research project. `_raise_for_status` (L62-76) converts a 404 into `HikerNotFoundError`; `ingest_reels`
(orchestrator.py L76-78) calls `fetch_user_clips_all` with no surrounding `try/except`, and `main()`'s
per-username loop (L216-221) has no `try/except` either. **Inference, not directly observed (this exact code
path was never run against the live API by the research project, so flagged as inferred rather than
confirmed):** a live run would very likely raise `HikerNotFoundError` on the very first call to
`fetch_user_clips`, before any `Reel` row is written, and that exception would propagate uncaught out of
`main()`, terminating the process on the first configured username. Under this reading, **no `Reel`,
`ReelMetric`, or `Comment` rows can exist from a genuine run of this pipeline** — those tables are expected to
be empty or to contain only rows inserted by some other path (manual seeds, tests).

`Account` rows are a different story: `fetch_user_by_username` already calls the correct, verified endpoint
(`/v2/user/by/username`), and `map_account` (mapper.py L62-76) already maps `follower_count`/`following_count`/
`media_count`/`username` correctly per `research-metrics.md` §A. Any `Account` rows that exist from a real run
are expected to be accurate and require no data migration — only the `pk`/`id` string-coercion cleanup from
Decision 3, which does not change already-correct values (they're already read as-is via `str(...)`, e.g.
`mapper.py` L64).

**Migration plan:**
1. `prisma migrate` to drop `ReelMetric.reach` (Decision 5). Safe as a plain `DROP COLUMN` — no code path ever
   wrote a non-null value into it (it was only ever populated from `reach_count`, a key `research-metrics.md`
   §B confirms is absent from every payload), so there is no real data to preserve or backfill.
2. No data backfill/repair step for existing `Reel`/`ReelMetric`/`Comment` rows: per the analysis above, none
   are expected to exist from a genuine run. If any are found in a given environment (e.g. from manual
   testing against a stub), they should be treated as untrustworthy — `videoUrl` on any such row is a signed
   CDN URL that has near-certainly expired (Decision 4), so there is no way to "repair" it in place regardless
   of what other fields say. The remediation is deletion-and-re-ingestion, not an in-place update.
3. Re-run ingestion (`hiker_ingestion.orchestrator.main`) per account after deploying the corrected client/
   mapper/orchestrator. This is a full re-fetch, not an incremental one — `Reel.instagramReelId` is `@unique`
   (schema.prisma L92) so re-ingesting an account that (against the analysis above) already has real rows
   will upsert cleanly via the existing `ON CONFLICT` clauses in `db.py` (`upsert_reel_metric`, L122-137).
4. No `Account` migration needed beyond the schema change in step 1 touching an unrelated table.

## Risks / Trade-offs

- **[Risk]** The inference in Decision 9 that no `Reel` rows currently exist is not directly verified against
  a live run of this exact code — it is derived from reading `_raise_for_status`/`ingest_reels`/`main`
  together, not from an observed stack trace. If some environment's HikerAPI account happened to accept
  `/v1/user/clips/chunk` (e.g. via an undocumented proxy/alias), this assumption would be wrong. →
  **Mitigation:** before dropping `ReelMetric.reach`, run a one-time count query
  (`SELECT count(*) FROM "Reel"`) in each target environment; if non-zero, treat step 2 of the migration plan
  as mandatory rather than a no-op.
- **[Risk]** `viralityScore` (Decision 6) is a genuinely new formula with no historical data to validate
  against — its weights (0.5 engagement / 0.3 share / 0.2 view-to-follower) are reasoned defaults, not tuned.
  → **Mitigation:** ship it, but treat the three weights as named constants rather than inlined literals so
  they can be recalibrated once real score distributions are observed, without a schema change.
- **[Risk]** Not calling `/v1/media/insight` (Decision 2) means this change never obtains
  `shopping_outbound_click_count`/`shopping_product_click_count`, or any other insight-only field, even though
  the endpoint is confirmed reachable. → **Mitigation:** none of those fields map to any current `ReelMetric`
  column, so this is a non-loss today; flagged as an Open Question if a future column needs them.
- **[Risk]** `viralityScore` carries no age term at all, so an old reel with strong lifetime numbers scores
  the same as a fresh breakout with identical rates — the score measures intensity, not momentum. →
  **Mitigation:** accepted for this change in exchange for determinism (Decision 6). Momentum is already
  observable by diffing consecutive `ReelSnapshot` rows, and a decayed score can be computed at query time
  for ranking without persisting a clock-dependent value.
- **[Trade-off]** Explicit per-endpoint unwrap functions (Decision 1) mean five small functions to maintain
  instead of one generic helper — more lines, but each one fails at the exact shape it assumes, rather than
  falling through a chain that can mask which endpoint actually changed shape.

## Open Questions

- Should `Reel.code` (shortcode) be added as a persisted column so a future job can call
  `/v2/media/info/by/code` without first re-listing clips? Decision 2 says no for this change, scoped by
  `proposal.md`'s Impact list; revisit if a near-term feature needs it.
- Should `ReelSnapshot.reach` (schema.prisma L186) be dropped alongside `ReelMetric.reach`? Same root cause
  (field never returned by any endpoint), but outside this proposal's stated Impact list — left for a
  follow-up change.
- Should `viralityScore` eventually incorporate the account's own historical reel distribution (a
  percentile/z-score against past performance) rather than only the single reel's own counts? Rejected for
  this change (Decision 6) for lack of a data-access path in `map_metric`'s current signature, not for lack
  of merit.
