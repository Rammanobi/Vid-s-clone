## ADDED Requirements

### Requirement: HikerAPI transport and authentication
The system SHALL send every HikerAPI request to base URL `https://api.hikerapi.com` and SHALL authenticate using an `x-access-key` header carrying the configured API token. No other header SHALL be used for authentication.

#### Scenario: Request carries the access-key header
- **WHEN** the client issues any HikerAPI request (profile, reels, comments, or media lookup)
- **THEN** the request is sent to a path under `https://api.hikerapi.com` with header `x-access-key: <token>` and no `Authorization` header is set

### Requirement: Profile endpoint selection
The system SHALL fetch account profile data from `GET /v2/user/by/username`, passing the `username` and `safe_int=true` query parameters.

#### Scenario: Resolving a username to a profile
- **WHEN** the orchestrator ingests the account `okaashish`
- **THEN** the client calls `GET /v2/user/by/username?username=okaashish&safe_int=true` and receives a response whose payload is the profile object

### Requirement: Reels endpoint selection and pagination
The system SHALL fetch a Reels list from `GET /v2/user/clips`, passing `user_id`, `safe_int=true`, and (on pages after the first) a `page_id` query parameter. The system SHALL read the pagination cursor from the top-level `next_page_id` response field and pass it as `page_id` on the next request. The system SHALL treat an empty or missing `next_page_id` as the end of the list and stop requesting further pages.

#### Scenario: First page request omits page_id
- **WHEN** the client fetches the first page of Reels for `user_id=45093317380`
- **THEN** the request is `GET /v2/user/clips?user_id=45093317380&safe_int=true` with no `page_id` parameter

#### Scenario: Subsequent page uses the returned cursor
- **WHEN** a `/v2/user/clips` response returns top-level `next_page_id="QVFEQkptQUFvVWNOdm5CSFpK..."`
- **THEN** the client's next request to `/v2/user/clips` includes `page_id=QVFEQkptQUFvVWNOdm5CSFpK...`

#### Scenario: Empty next_page_id ends pagination
- **WHEN** a `/v2/user/clips` response's top-level `next_page_id` is empty or absent
- **THEN** the client stops requesting further pages and returns the items collected so far

### Requirement: Comments endpoint selection and pagination
The system SHALL fetch comments for a media item from `GET /v2/media/comments`, passing an `id` query parameter (not `media_id`) identifying the media, plus `safe_int=true`. The system SHALL read the array of comments from `response.comments`, not `response.items`.

#### Scenario: Fetching comments for a media item
- **WHEN** the client fetches comments for media `3944679501543145356_45093317380`
- **THEN** the request is `GET /v2/media/comments?id=3944679501543145356_45093317380&safe_int=true`, and the client reads comment objects from `response.comments`

### Requirement: Response envelope unwrapping
The system SHALL unwrap each HikerAPI response according to that endpoint's specific envelope shape, since no single envelope structure applies across endpoints:
- `/v2/user/by/username` → the profile object is at `user`
- `/v2/user/clips` → each Reel is at `response.items[].media` (double-nested: the array element itself is `{"media": {...}}`, not the media object directly)
- `/v2/media/comments` → each comment is at `response.comments[]` (flat elements, no further nesting)
- `/v2/media/info/by/code` → the media object is at `media_or_ad`
- `/v1/media/insight` → the payload fields sit directly at the JSON root, with no wrapper key at all

#### Scenario: Unwrapping a profile response
- **WHEN** `/v2/user/by/username` returns `{"status": "ok", "user": {"pk": 45093317380, "username": "okaashish", ...}}`
- **THEN** the system reads the profile fields from the `user` object, not from the response root

#### Scenario: Unwrapping a double-nested clips item
- **WHEN** a `/v2/user/clips` response contains `{"response": {"items": [{"media": {"pk": "3944679501543145356", "code": "Da-URtaPn-M", ...}}]}}`
- **THEN** the system extracts the Reel fields from `response.items[0].media`, not from `response.items[0]` directly

#### Scenario: Unwrapping a comments response
- **WHEN** a `/v2/media/comments` response contains `{"response": {"comments": [{"pk": "18209380177352304", "text": "Certificate", "created_at": 1784474021}]}}`
- **THEN** the system extracts comment fields from `response.comments[0]`, not from a top-level `items` key

#### Scenario: Unwrapping a media-by-code response
- **WHEN** `/v2/media/info/by/code` returns `{"status": "ok", "media_or_ad": {"pk": "3944679501543145356", "play_count": 11875, ...}}`
- **THEN** the system reads media fields from `media_or_ad`, not from the response root

#### Scenario: Unwrapping a flat insight response
- **WHEN** `/v1/media/insight` returns `{"id": "18131938045622606", "like_count": 132, "save_count": null, ...}` with no wrapper key
- **THEN** the system reads fields directly from the response root

### Requirement: Reel identification signature
The system SHALL identify a media item as a Reel using the combination `product_type == "clips"` and `media_type == 2`.

#### Scenario: Confirming a media item is a Reel
- **WHEN** a media object has `"product_type": "clips"` and `"media_type": 2`
- **THEN** the system treats the item as a Reel eligible for ingestion into the `Reel` table

### Requirement: Account field extraction
The system SHALL extract account fields from the unwrapped profile object as follows: `instagramId` from `pk` (or `id` when `pk` is absent), `username` from `username`, `followerCount` from `follower_count`, `followingCount` from `following_count`, and `postsCount` from `media_count`.

#### Scenario: Mapping a profile object to AccountData
- **WHEN** the unwrapped profile is `{"pk": 45093317380, "username": "okaashish", "follower_count": 150165, "following_count": 389, "media_count": 533}`
- **THEN** the system produces `instagramId="45093317380"`, `username="okaashish"`, `followerCount=150165`, `followingCount=389`, `postsCount=533`

### Requirement: Reel field extraction
The system SHALL extract Reel fields from the unwrapped media object as follows:
- `instagramReelId` from `pk`
- `videoUrl` from `video_versions[0].url` (the top-level `video_url` key does not exist and SHALL NOT be relied upon)
- `caption` from `caption.text` when `caption` is an object (the raw `caption` field is always an object, never a bare string)
- `durationSec` from `video_duration`
- `postedAt` from `taken_at`, interpreted as Unix seconds in UTC

#### Scenario: Mapping a media object to ReelData
- **WHEN** the unwrapped media object is `{"pk": "3944679501543145356", "code": "Da-URtaPn-M", "video_versions": [{"url": "https://scontent-ord5-3.cdninstagram.com/o1/v/t2/...oe=6A63A43B"}], "caption": {"text": "Comment \"certificate\" and I'll send you the official links.\n"}, "video_duration": 39.75, "taken_at": 1784462647}`
- **THEN** the system produces `instagramReelId="3944679501543145356"`, `videoUrl="https://scontent-ord5-3.cdninstagram.com/o1/v/t2/...oe=6A63A43B"`, `caption="Comment \"certificate\" and I'll send you the official links.\n"`, `durationSec=39.75`, and `postedAt` equal to the UTC datetime for Unix timestamp `1784462647`

#### Scenario: Caption object without a usable text field
- **WHEN** the unwrapped media object's `caption` is `null` or an object with no `text` key
- **THEN** the system produces `caption=null` rather than raising an error or stringifying the raw object

### Requirement: Comment field extraction and isCreator derivation
The system SHALL extract `authorId` from a comment's `user.pk`, `text` from `text`, and `postedAt` from `created_at` (Unix seconds, UTC). The system SHALL derive `isCreator` by comparing the comment's `user.pk` to the media owner's `pk`; it SHALL NOT rely on an `is_created_by_media_owner` field, since that field is absent (not `false`) on ordinary top-level comments.

#### Scenario: Deriving isCreator for a non-owner comment
- **WHEN** a comment has `user.pk = 47831239820` and the media owner's `pk` is `45093317380`
- **THEN** the system sets `isCreator=false` for that comment, without inspecting any `is_created_by_media_owner` field

#### Scenario: Deriving isCreator for the owner's own comment
- **WHEN** a comment has `user.pk = 45093317380` and the media owner's `pk` is `45093317380`
- **THEN** the system sets `isCreator=true` for that comment

### Requirement: ID type tolerance under safe_int
The system SHALL send `safe_int=true` on every `/v2/*` request (all endpoints except `/v1/media/insight`, which never sends `safe_int`) and SHALL accept identifier fields (`pk`, `pk_id`, `id`, `strong_id__`) as either a JSON number or a JSON string without raising a type error.

#### Scenario: Numeric pk on a small account ID
- **WHEN** a profile response returns `"pk": 45093317380` as a JSON number
- **THEN** the system converts it to the string `"45093317380"` for `instagramId` without error

#### Scenario: String pk on a large media ID
- **WHEN** a clips response returns `"pk": "3944679501543145356"` as a JSON string
- **THEN** the system uses it directly as `instagramReelId` without error

### Requirement: HikerAPI error handling
The system SHALL raise a distinct, identifiable error for HTTP 401 (authentication failure), HTTP 404 (resource not found), and HTTP 402 with an `InsufficientFunds` body (credit exhaustion). The system SHALL NOT implement or assume any rate-limit/`Retry-After`/429 retry behavior, since no evidence of HikerAPI rate limiting exists and the only documented non-2xx failure mode is credit exhaustion.

#### Scenario: Credit exhaustion is reported distinctly
- **WHEN** a HikerAPI response has status code 402 and a body containing `{"exc_type": "InsufficientFunds"}`
- **THEN** the system raises an insufficient-funds error distinct from a generic HTTP error, rather than retrying

#### Scenario: Authentication failure is reported distinctly
- **WHEN** a HikerAPI response has status code 401
- **THEN** the system raises an authentication error and does not retry the request

#### Scenario: Not-found is reported distinctly
- **WHEN** a HikerAPI response has status code 404
- **THEN** the system raises a not-found error and does not retry the request

#### Scenario: No 429 handling is invoked
- **WHEN** a HikerAPI response has any status code other than 401, 404, or 402-with-InsufficientFunds
- **THEN** the system does not apply any rate-limit-specific wait, backoff, or `Retry-After` handling
