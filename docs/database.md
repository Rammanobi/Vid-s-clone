# Database Schema

## Enums

```prisma
enum HookType {
  CURIOSITY       // "you won't believe...", "mind blown"
  CONTRARIAN      // "hot take", "unpopular opinion"
  STORY           // "let me tell you a story"
  PROBLEM_SOLUTION // "how to", "step by step"
  QUESTION        // "why", "what", "how", "do you"
  OTHER
}

enum ContentFormat {
  TUTORIAL          // how-to guides, step-by-step
  BEHIND_THE_SCENES // bts, exclusive looks
  TALKING_HEAD      // monologue, explanation
  SCREEN_RECORDING  // screen capture, desktop
  SKIT              // comedy, parody, humor
  OTHER
}

enum MetricQuality {
  FULL      // saves + shares available
  PARTIAL   // saves or shares missing
}
```

## Models

### Account & Creator Knowledge Layer

```
Account
├── id: String @id @default(uuid())
├── instagramId: String @unique
├── username: String @unique
├── followerCount: Int
├── followingCount: Int
├── postsCount: Int
├── isCompetitor: Boolean
├── createdAt: DateTime
├── updatedAt: DateTime
├── reels: Reel[]
├── snapshots: AccountSnapshot[]
├── creatorProfile: CreatorProfile?
└── @@index([username])

CreatorProfile
├── id: String @id
├── accountId: String @unique → Account
├── bestTopics: String[]
├── worstTopics: String[]
├── bestHookTypes: HookType[]
├── bestPostingDay: String?
├── bestDurationRange: String?
├── bestContentFormat: ContentFormat?
├── audienceInterests: String[]
└── updatedAt: DateTime

AccountSnapshot
├── id: String @id
├── accountId: String → Account
├── followerCount: Int
├── snapshotAt: DateTime
└── @@index([accountId, snapshotAt])
```

### Reels, Multimodal & Hybrid Vector Search

```
Reel
├── id: String @id @default(uuid())
├── accountId: String → Account
├── instagramReelId: String @unique
├── videoUrl: String
├── caption: String? @db.Text
├── durationSec: Float
├── postedAt: DateTime
├── transcript: String? @db.Text
├── transcriptJson: Json?
├── visualTopics: String[]
├── textOverlays: String[]
├── visualSummary: String? @db.Text
├── combinedEmbedding: vector(1536)?  [pgvector HNSW index]
├── searchVector: tsvector?            [GIN index, auto-synced]
├── metrics: ReelMetric?
├── metricSnapshots: ReelSnapshot[]
├── intelligence: ContentIntelligence?
├── comments: Comment[]
├── createdAt: DateTime
├── updatedAt: DateTime
└── @@index([accountId, postedAt])

ContentIntelligence
├── id: String @id
├── reelId: String @unique → Reel
├── topic: String?
├── hookType: HookType?
├── hookText: String?
├── cta: String?
├── contentFormat: ContentFormat?
├── teachingStyle: String?
├── narrativeStyle: String?
├── audienceIntent: String?
├── sentiment: String?
├── visualStyle: String?
├── createdAt: DateTime
├── updatedAt: DateTime
└── @@index([topic]), @@index([hookType]), @@index([teachingStyle])
```

### Analytics Layer

```
ReelMetric
├── id: String @id
├── reelId: String @unique → Reel
├── views: Int
├── likes: Int
├── commentsCount: Int
├── saves: Int?
├── shares: Int?
├── reach: Int?
├── engagementRate: Float
├── saveRate: Float?
├── shareRate: Float?
├── commentRate: Float?
├── viralityScore: Float
├── viewToFollower: Float
├── metricQuality: MetricQuality
├── isVolatile: Boolean
├── calculatedAt: DateTime
├── updatedAt: DateTime
└── @@index([viralityScore]), @@index([engagementRate])

ReelSnapshot             [time-series drift tracking]
├── id: String @id
├── reelId: String → Reel
├── views: Int
├── likes: Int
├── commentsCount: Int
├── saves: Int?
├── shares: Int?
├── reach: Int?
├── snapshotAt: DateTime
└── @@index([reelId, snapshotAt])

Comment
├── id: String @id
├── reelId: String → Reel
├── authorId: String
├── text: String @db.Text
├── isCreator: Boolean
├── postedAt: DateTime
└── @@index([reelId])
```

### Competitor & Trend Stores

```
CompetitorInsight
├── id: String @id
├── competitorId: String
├── niche: String
├── winningFormat: ContentFormat?
├── topTopics: String[]
├── avgVirality: Float
├── updatedAt: DateTime
└── @@index([niche])

TrendStore
├── id: String @id
├── topic: String
├── hookPattern: String?
├── contentFormat: ContentFormat?
├── viralityScore: Float
├── detectedAt: DateTime
└── @@index([topic]), @@index([viralityScore])
```

### Agent Execution & LangGraph State

```
Session
├── id: String @id
├── userId: String
├── summary: String? @db.Text
├── createdAt: DateTime
├── updatedAt: DateTime
├── messages: ChatMessage[]
└── agentRuns: AgentExecutionLog[]

ChatMessage
├── id: String @id
├── sessionId: String → Session
├── role: String                    # "user" | "assistant"
├── content: String @db.Text
├── citations: Json?                # [{source, type, summary}]
├── createdAt: DateTime
└── @@index([sessionId, createdAt])

AgentExecutionLog
├── id: String @id
├── sessionId: String → Session
├── intent: String?
├── retrievalPlan: Json?
├── confidenceScore: Float?
├── routingDecision: String?
├── createdAt: DateTime
└── @@index([sessionId])
```

## Neon-Init SQL (prisma/neon-init.sql)

```sql
-- 1. Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. HNSW index for dense vector search
CREATE INDEX IF NOT EXISTS reel_embedding_hnsw_idx
ON "Reel" USING hnsw ("combinedEmbedding" vector_cosine_ops);

-- 3. GIN index for BM25 keyword search
CREATE INDEX IF NOT EXISTS reel_sparse_bm25_idx
ON "Reel" USING gin ("searchVector");

-- 4. Auto-sync tsvector trigger
CREATE OR REPLACE FUNCTION update_reel_search_vector() RETURNS trigger AS $$
begin
  new."searchVector" :=
    setweight(to_tsvector('english', coalesce(new.caption, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(new.transcript, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(new."visualSummary", '')), 'C');
  return new;
end
$$ LANGUAGE plpgsql;

CREATE TRIGGER reel_search_vector_update BEFORE INSERT OR UPDATE
ON "Reel" FOR EACH ROW EXECUTE FUNCTION update_reel_search_vector();
```

Search vector weights: caption (A) > transcript (B) > visual_summary (C).

## Example Queries

```sql
-- Top virality reels
SELECT * FROM "ReelMetric" ORDER BY "viralityScore" DESC LIMIT 10;

-- Reels with best engagement for a specific topic
SELECT r."caption", r."postedAt", rm."engagementRate", ci."topic"
FROM "Reel" r
JOIN "ReelMetric" rm ON rm."reelId" = r."id"
JOIN "ContentIntelligence" ci ON ci."reelId" = r."id"
WHERE ci."topic" ILIKE '%fitness%'
ORDER BY rm."engagementRate" DESC;

-- Trending topics
SELECT topic, COUNT(*) as count, AVG("viralityScore") as avg_virality
FROM "TrendStore" GROUP BY topic ORDER BY avg_virality DESC;

-- Drift: reels where current engagement differs significantly from initial snapshot
SELECT r."id", rm."engagementRate", rs."engagementRate" as initial_rate
FROM "Reel" r
JOIN "ReelMetric" rm ON rm."reelId" = r."id"
JOIN "ReelSnapshot" rs ON rs."reelId" = r."id"
WHERE rs."snapshotAt" = (SELECT MIN("snapshotAt") FROM "ReelSnapshot" WHERE "reelId" = r."id")
  AND ABS(rm."engagementRate" - rs."engagementRate") > 1.0;
```
