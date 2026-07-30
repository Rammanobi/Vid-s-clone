# Reel Bot — Instagram Reel Analysis & Chat

A self-contained MVP module for analyzing Instagram reels and having AI-powered conversations about them.

## Overview

Reel Bot is a two-phase system:
1. **Ingestion Phase**: Connect an Instagram handle, fetch the latest 20 reels, extract transcripts, and analyze content
2. **Chat Phase**: Ask questions about the reels and get data-grounded AI responses

No login required — it works with public Instagram accounts only.

## Architecture

The module is completely isolated in `app/reel_bot/`:
- **Own database pool** (asyncpg, separate from main app)
- **Own API credentials** (Hiker API token, LLM key)
- **Own Prisma models** (ReelBotReel, ReelBotSession, ReelBotChatMessage)
- **Public endpoints** (no authentication required, rate-limited)

## Prerequisites

### Backend
- Python 3.14+
- FastAPI, uvicorn
- asyncpg (for Postgres)
- httpx (for API calls)
- FFmpeg (for audio extraction)

### Frontend
- Node.js 18+
- Next.js 15+
- npm or yarn

### External Services
- **Postgres database** (same instance as main app)
- **Hiker API account** (Instagram scraping)
- **LLM API** (OpenAI-compatible, tested with OpenAI and Groq)
- **Cloudflare Tunnel** (optional, for public access)

## Setup

### 1. Environment Variables

Create or update `.env` in the project root:

```bash
# Reel Bot (isolated module)
REEL_BOT_HIKER_API_TOKEN=your_hiker_api_token_here
REEL_BOT_HIKER_BASE_URL=https://api.hikerapi.com

REEL_BOT_LLM_API_KEY=your_openai_or_groq_key_here
REEL_BOT_LLM_BASE_URL=https://api.openai.com/v1
REEL_BOT_LLM_MODEL=gpt-4o-mini

REEL_BOT_MAX_REELS=20
REEL_BOT_MEMORY_WINDOW=10

# For Cloudflare Tunnel (optional)
CORS_ORIGINS=https://your-frontend-tunnel.trycloudflare.com
```

### 2. Database Setup

The Reel Bot uses new Prisma models. Apply the schema:

```bash
# From project root
npx prisma db push
```

This creates three new tables:
- `ReelBotReel` — Instagram reel data (transcript, stats, keywords)
- `ReelBotSession` — Chat sessions per Instagram handle
- `ReelBotChatMessage` — Message history (user + assistant)

### 3. FFmpeg

Required for audio extraction. Install:
- **Windows**: Download from https://ffmpeg.org/download.html or use `choco install ffmpeg`
- **Mac**: `brew install ffmpeg`
- **Linux**: `apt-get install ffmpeg`

Verify: `ffmpeg -version`

## Running Locally

### Terminal 1 — Backend

```powershell
cd C:\Users\aseem\Vid-s-clone
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will:
- Initialize Reel Bot's isolated database pool
- Mount `/reel-bot/ingest` and `/reel-bot/chat` endpoints
- Apply CORS middleware (configured for localhost by default)

### Terminal 2 — Frontend (Production Mode)

```powershell
cd C:\Users\aseem\Vid-s-clone\frontend
npm run build -- --webpack
npm start
```

The frontend will:
- Build Next.js app with webpack (not turbopack, for Windows compatibility)
- Start production server on http://localhost:3000
- Read `NEXT_PUBLIC_API_URL=http://localhost:8000` from `.env.local`

### Visit

Open http://localhost:3000/reel-bot

## Using Reel Bot

### Phase 1: Ingestion

1. Enter an Instagram handle (e.g., `@username`)
2. Click "Connect"
3. Reel Bot will:
   - Fetch the 20 most recent public reels
   - Download each video
   - Extract audio and transcribe with Groq Whisper API (2s per reel)
   - Analyze transcripts (WPM, keywords)
   - Store in database

**Timeline**: ~30-40 seconds for 20 reels (10x faster than local Whisper)

### Phase 2: Chat

Once ingestion completes:
1. Ask questions about the reels (e.g., "Which reel had the highest engagement?")
2. Reel Bot retrieves recent reels from database
3. Builds a prompt with reel data (transcript, views, likes, keywords)
4. Sends to LLM and returns data-grounded response

**System Prompt**: Enforces strict data grounding — LLM refuses generic advice and quotes transcripts directly. Edit it live at `PUT /admin/prompts/reel_bot_chat` (see "Live-editable prompts" below) — no redeploy needed.

### Caching

Reconnecting an already-ingested handle no longer always re-fetches from Hiker. If the handle's stored reels were updated within `REEL_BOT_CACHE_HOURS` (default 24), ingestion serves the cached rows from Neon instead of a live Hiker call — saves API credits and ~30-45s on repeat connects. Force a fresh fetch by deleting the handle's `ReelBotReel` rows, or lowering `REEL_BOT_CACHE_HOURS`.

### Reel hyperlinks

Chat responses reference reels as clickable links instead of "Reel N" — e.g. "the GitHub Claude Code reel" links straight to the real `instagram.com/reel/{code}/` post. Requires the `permalink` column (backfilled automatically on next ingest for any handle ingested before this feature shipped).

## Public Access (Cloudflare Tunnel)

### Setup

#### Terminal 3 — Backend Tunnel

```powershell
cloudflared tunnel --url http://localhost:8000
```

This outputs:
```
Your quick Tunnel has been created! Visit it at:
https://honest-voters-dame-charles.trycloudflare.com
```

#### Terminal 4 — Frontend Tunnel

```powershell
cloudflared tunnel --url http://localhost:3000
```

This outputs:
```
Your quick Tunnel has been created! Visit it at:
https://run-familiar-diego-signing.trycloudflare.com
```

### Configure Frontend for Tunnel

Update `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://honest-voters-dame-charles.trycloudflare.com
```

### Visit

Open https://run-familiar-diego-signing.trycloudflare.com/reel-bot

## API Endpoints

### POST /reel-bot/ingest

**Request:**
```json
{
  "instagram_handle": "username"
}
```

**Response:**
```json
{
  "instagram_handle": "username",
  "reels_synced": 20,
  "avg_wpm": 145.3,
  "top_keywords": ["content", "strategy", "growth", "engagement", "analytics"]
}
```

**Rate Limit**: 5 requests/hour (protects Hiker API credits)

### POST /reel-bot/chat

**Request:**
```json
{
  "instagram_handle": "username",
  "session_id": null,
  "message": "Which reel had the most views?"
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "response": "Your most-viewed reel is 'Content Strategy Tips' with 15,234 views..."
}
```

**Rate Limit**: 20 requests/minute (LLM cost protection)

## Troubleshooting

### "FFmpeg not found"
- Install FFmpeg (see Prerequisites)
- Verify: `ffmpeg -version`
- If on Windows, add FFmpeg to PATH or restart terminal

### "Invalid Hiker API token"
- Check `REEL_BOT_HIKER_API_TOKEN` in `.env`
- Verify token is valid in Hiker dashboard
- Ensure token has access to user/clips endpoints

### "Transcript is NULL"
- Check FFmpeg installation
- Verify video URL is valid (check Hiker API response)
- Check Groq API key is valid (`REEL_BOT_LLM_API_KEY`)

### "CORS errors (local)"
- Check `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`
- Restart frontend dev server after env changes
- Backend CORS defaults to allowing localhost

### "WebSocket HMR errors (tunnel)"
- Normal when using frontend in dev mode through tunnel
- Cloudflare Tunnel doesn't proxy WebSocket HMR
- Solution: Use production build (`npm run build && npm start`)

### LLM returning generic advice instead of reel data
- Check system prompt in `app/reel_bot/reel_chat_engine.py`
- Verify transcripts are being extracted (`SELECT * FROM "ReelBotReel" WHERE "rawTranscript" IS NOT NULL`)
- Test with a handle that has audio-only reels (not just videos)

## Performance

- **Ingestion**: 20-30 seconds for 20 reels (Groq Whisper: 2s/reel, parallelized)
- **Chat response**: 2-5 seconds (LLM inference time)
- **Database queries**: <100ms (minimal data, indexed lookups)

## Database Schema

### ReelBotReel
```sql
id (UUID, PK)
instagramHandle (string)
instagramReelId (string, unique per handle)
videoUrl (string)
permalink (string, nullable) — public https://instagram.com/reel/{code}/ link, used for chat hyperlinks
caption (text, nullable)
views, likes, commentsCount, shares (int)
durationSec (float)
postedAt (timestamp)
rawTranscript (text, nullable) — raw output from Groq
cleanTranscript (text, nullable) — cleaned text
wordCount, wpm (int, nullable)
topKeywords (string[]) — top 3-5 keywords
createdAt, updatedAt (timestamp) — updatedAt drives the 24h ingestion cache
```

### ReelBotSession
```sql
id (UUID, PK)
instagramHandle (string)
createdAt, updatedAt (timestamp)
messages (ReelBotChatMessage[]) — relation
```

### ReelBotChatMessage
```sql
id (UUID, PK)
sessionId (UUID, FK)
role (string) — 'user' | 'assistant'
content (text)
createdAt (timestamp)
```

## Live-editable prompts (Neon, no redeploy)

All 6 LLM system prompts across the app — including `reel_bot_chat` — live in a
`SystemPrompt` table in Neon, not just hardcoded strings. An in-process cache
(`app/prompts.py`) is loaded at startup and refreshed on every write, so editing
a prompt takes effect on the very next request — no restart, no redeploy.

```bash
# List current prompts + whether each is coming from the DB, an env var, or the built-in default
GET /admin/prompts

# Edit one live
PUT /admin/prompts/reel_bot_chat
{ "content": "new prompt text..." }
```

Precedence: DB row > env var (`PROMPT_REEL_BOT_CHAT` etc.) > built-in default in
`app/prompts.py`. Both endpoints require the same admin auth as the rest of the API.

## Development Notes

- **Isolation**: No imports from main app except `app.config` (for DATABASE_URL) and `app.transcription.processor` (for Whisper wrapper)
- **Credentials**: Each service (Hiker, LLM) has its own isolated client with own API keys
- **Error handling**: Public endpoints return 4xx/5xx errors with detail messages; rate limits return 429
- **Logging**: Structured JSON logs via `app.logging_setup`
- **No authentication**: All endpoints are public; cost protection via rate limiting only

## Changelog

### 2026-07-30
- Moved all 6 LLM system prompts (including this module's) from code/env vars into a Neon `SystemPrompt` table, editable live via `GET`/`PUT /admin/prompts/{key}` with zero redeploy.
- Fixed the chat engine over-using markdown tables: qualitative/strategic questions ("what's the vibe of my content?", "should I post more often?") were returning full metrics tables instead of prose. Tightened `reel_bot_chat` (and `reasoner`) to use tables only for explicit comparison/ranking/table requests.
- Fixed literal `<br>` tags rendering as visible text instead of line breaks in the frontend's markdown renderer.
- Added a "24-hour ingestion cache": reconnecting an already-ingested handle now serves stored Neon data instead of re-calling Hiker + re-transcribing, when the data is still fresh (`REEL_BOT_CACHE_HOURS`, default 24).
- Reels are now referenced as clickable hyperlinks to the real Instagram post (e.g. "the GitHub Claude Code reel") instead of "Reel N" - backed by a new `permalink` column captured from Hiker's `code` field at ingest time.

## Future Improvements

- [ ] Persistent named Cloudflare tunnel (instead of ephemeral URLs)
- [ ] User authentication (optional OAuth via Instagram)
- [ ] Multi-handle support (track favorite creators)
- [ ] Webhook notifications (when new reels are detected)
- [ ] Advanced analytics (engagement trends, posting schedule recommendations)
- [ ] Video thumbnails in chat (show reel preview images)

## Support

For issues or questions:
1. Check `.env` configuration is complete
2. Verify FFmpeg and external services are working
3. Check backend logs for detailed error messages
4. Inspect database tables to verify data is being stored

---

Built with ❤️ as an isolated, self-contained Instagram Reel analysis chatbot.
