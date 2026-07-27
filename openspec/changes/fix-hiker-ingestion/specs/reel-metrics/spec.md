## ADDED Requirements

### Requirement: Views sourced from play_count
The system SHALL derive `views` from the `play_count` field on the media object. The system SHALL NOT read a `view_count` or `views` field, since no such key exists anywhere in the HikerAPI payload for Reels — it is structurally absent, not merely null.

#### Scenario: Views mapped from play_count
- **WHEN** a media object has `"play_count": 11875` and no `view_count` key at all
- **THEN** the system sets `views=11875`

#### Scenario: play_count equals the sum of its platform components
- **WHEN** a media object has `"ig_play_count": 8152` and `"fb_play_count": 3723` alongside `"play_count": 11875`
- **THEN** the system still reads `views` from `play_count` (11875), treating `ig_play_count`/`fb_play_count` as informational components rather than the source of `views`

### Requirement: Likes, comment count, and saves mapping
The system SHALL derive `likes` from `like_count`, `commentsCount` from `comment_count`, and `saves` from `save_count`.

#### Scenario: Mapping likes, commentsCount, and saves
- **WHEN** a media object has `"like_count": 146`, `"comment_count": 122`, and `"save_count": 136`
- **THEN** the system sets `likes=146`, `commentsCount=122`, and `saves=136`

### Requirement: Shares mapping
The system SHALL derive `shares` from `reshare_count`. The system SHALL NOT read a `share_count` field, since that field name does not exist in the payload, and SHALL NOT read `media_repost_count`, since that field measures Instagram's separate "Repost" feature and is a materially smaller, different metric.

#### Scenario: Shares mapped from reshare_count, not media_repost_count
- **WHEN** a media object has `"reshare_count": 74` and `"media_repost_count": 12` (no `share_count` key present)
- **THEN** the system sets `shares=74`, not `12`

### Requirement: Reach and impressions are unavailable
The system SHALL NOT include `reach` or `impressions` in the ingested metric contract. Neither field exists anywhere in the HikerAPI payload for Reels; the one reach-adjacent key observed (`creator_marketplace_accounts_reached_metric`) is an unrelated, always-null brand-partnership field and SHALL NOT be treated as a source of `reach`.

#### Scenario: No reach or impressions field is populated
- **WHEN** the system maps a media object to reel metric data
- **THEN** the resulting record has no `reach` or `impressions` value, and this absence alone does not affect any other derived field

### Requirement: Engagement rate derivation
The system SHALL compute `engagementRate` as `(likes + commentsCount + saves + shares) / views * 100`, rounded to 4 decimal places, where any of `likes`, `commentsCount`, `saves`, `shares` that is null is treated as `0` for the purpose of this sum. When `views` is `0` or unavailable, the system SHALL set `engagementRate` to `0` without performing the division.

#### Scenario: Computing engagementRate from a populated reel
- **WHEN** a reel has `views=11875`, `likes=146`, `commentsCount=122`, `saves=136`, `shares=74`
- **THEN** the system computes `engagementRate = (146 + 122 + 136 + 74) / 11875 * 100 = 4.0253`

#### Scenario: Zero views guards engagementRate
- **WHEN** a reel has `views=0`
- **THEN** the system sets `engagementRate=0` without dividing by `views`

### Requirement: Save rate derivation
The system SHALL compute `saveRate` as `saves / views * 100`, rounded to 4 decimal places. When `views` is `0` or unavailable, or when `saves` is null, the system SHALL set `saveRate` to `0` without performing the division.

#### Scenario: Computing saveRate from a populated reel
- **WHEN** a reel has `views=11875` and `saves=136`
- **THEN** the system computes `saveRate = 136 / 11875 * 100 = 1.1453`

#### Scenario: Zero views guards saveRate
- **WHEN** a reel has `views=0` and `saves=136`
- **THEN** the system sets `saveRate=0` without dividing by `views`

### Requirement: Share rate derivation
The system SHALL compute `shareRate` as `shares / views * 100`, rounded to 4 decimal places. When `views` is `0` or unavailable, or when `shares` is null, the system SHALL set `shareRate` to `0` without performing the division.

#### Scenario: Computing shareRate from a populated reel
- **WHEN** a reel has `views=11875` and `shares=74`
- **THEN** the system computes `shareRate = 74 / 11875 * 100 = 0.6232`

#### Scenario: Zero views guards shareRate
- **WHEN** a reel has `views=0` and `shares=74`
- **THEN** the system sets `shareRate=0` without dividing by `views`

### Requirement: Comment rate derivation
The system SHALL compute `commentRate` as `commentsCount / views * 100`, rounded to 4 decimal places. When `views` is `0` or unavailable, the system SHALL set `commentRate` to `0` without performing the division.

#### Scenario: Computing commentRate from a populated reel
- **WHEN** a reel has `views=11875` and `commentsCount=122`
- **THEN** the system computes `commentRate = 122 / 11875 * 100 = 1.0274`

#### Scenario: Zero views guards commentRate
- **WHEN** a reel has `views=0` and `commentsCount=122`
- **THEN** the system sets `commentRate=0` without dividing by `views`

### Requirement: View-to-follower rate derivation
The system SHALL compute `viewToFollower` as `views / followerCount * 100`, rounded to 4 decimal places. When `followerCount` is `0` or unavailable, the system SHALL set `viewToFollower` to `0` without performing the division.

#### Scenario: Computing viewToFollower from a populated account
- **WHEN** a reel has `views=11875` and the account has `followerCount=150165`
- **THEN** the system computes `viewToFollower = 11875 / 150165 * 100 = 7.9080`

#### Scenario: Zero followers guards viewToFollower
- **WHEN** the account has `followerCount=0`
- **THEN** the system sets `viewToFollower=0` without dividing by `followerCount`

### Requirement: Virality score formula
The system SHALL compute `viralityScore` as the deterministic weighted composite `(engagementRate * 0.5) + (shareRate * 0.3) + (viewToFollower * 0.2)`, rounded to 4 decimal places, using the already-computed and already-zero-guarded `engagementRate`, `shareRate`, and `viewToFollower` values. Because each input is independently zero-guarded, `viralityScore` SHALL always be computable and SHALL be `0` when `views` and `followerCount` are both `0` or unavailable.

#### Scenario: Computing viralityScore from a populated reel
- **WHEN** a reel has `engagementRate=4.0253`, `shareRate=0.6232`, and `viewToFollower=7.9080`
- **THEN** the system computes `viralityScore = (4.0253 * 0.5) + (0.6232 * 0.3) + (7.9080 * 0.2) = 3.7812`

#### Scenario: Zero inputs produce a zero virality score
- **WHEN** a reel has `views=0` and the account has `followerCount=0`, so `engagementRate=0`, `shareRate=0`, and `viewToFollower=0`
- **THEN** the system computes `viralityScore=0` without any division taking place

### Requirement: Metric quality classification
The system SHALL set `metricQuality` to `FULL` when `views`, `likes`, `commentsCount`, `saves`, and `shares` are all non-null. The system SHALL set `metricQuality` to `PARTIAL` when any of those five fields is null. Because `reach` and `impressions` are never returned by this API, they SHALL be excluded from the `FULL`/`PARTIAL` determination entirely — their permanent absence SHALL NOT prevent a reel from reaching `FULL`.

#### Scenario: All core fields present yields FULL
- **WHEN** a reel has `views=11875`, `likes=146`, `commentsCount=122`, `saves=136`, `shares=74` (with no `reach` or `impressions` value at all)
- **THEN** the system sets `metricQuality=FULL`

#### Scenario: A null core field yields PARTIAL
- **WHEN** a reel has `views=11875`, `likes=132`, `commentsCount=114`, `shares=74`, but the API returned `"save_count": null` for that media (as observed for media id `18131938045622606`)
- **THEN** the system sets `saves=null` and `metricQuality=PARTIAL`

### Requirement: Derived rates never raise ZeroDivisionError
No derived rate computation (`engagementRate`, `saveRate`, `shareRate`, `commentRate`, `viewToFollower`, `viralityScore`) SHALL raise `ZeroDivisionError` under any input, including `views=0`, `followerCount=0`, or either value being unavailable/null.

#### Scenario: Computing all rates for a reel with zero views and zero followers
- **WHEN** a reel has `views=0`, `likes=10`, `commentsCount=2`, `saves=1`, `shares=0`, and the account has `followerCount=0`
- **THEN** the system returns `engagementRate=0`, `saveRate=0`, `shareRate=0`, `commentRate=0`, `viewToFollower=0`, and `viralityScore=0`, with no exception raised
