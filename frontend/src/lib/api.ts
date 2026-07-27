const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface RequestOptions extends RequestInit {
  token?: string
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { token, ...fetchOptions } = options
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }

  return response.json()
}

export const api = {
  get: <T>(endpoint: string, token?: string) =>
    request<T>(endpoint, { method: "GET", token }),

  post: <T>(endpoint: string, body?: unknown, token?: string) =>
    request<T>(endpoint, { method: "POST", body: body ? JSON.stringify(body) : undefined, token }),

  put: <T>(endpoint: string, body?: unknown, token?: string) =>
    request<T>(endpoint, { method: "PUT", body: JSON.stringify(body), token }),

  health: {
    check: (token?: string) => api.get<ApiHealth>("/health", token),
    analytics: () => api.get<ApiHealth>("/analytics/health"),
    content: () => api.get<ApiHealth>("/content/health"),
    creator: () => api.get<ApiHealth>("/creator/health"),
    knowledge: () => api.get<ApiHealth>("/knowledge/health"),
    pipeline: (token?: string) => api.get<PipelineHealth>("/pipeline/health", token),
  },

  auth: {
    login: (username: string, password: string) => {
      const formData = new URLSearchParams()
      formData.append("username", username)
      formData.append("password", password)
      return fetch(`${API_URL}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      }).then(async (res) => {
        if (!res.ok) throw new Error("Invalid credentials")
        return res.json() as Promise<{ access_token: string; token_type: string }>
      })
    },
    me: (token: string) => api.get<{ user: string }>("/auth/me", token),
  },

  session: {
    list: (token: string) => api.get<SessionsResponse>("/sessions", token),
    create: (token: string) => api.post<Session>("/sessions", {}, token),
    get: (token: string, id: string) => api.get<Session>(`/sessions/${id}`, token),
    messages: (token: string, id: string) =>
      api.get<MessagesResponse>(`/sessions/${id}/messages`, token),
    addMessage: (token: string, sessionId: string, content: string) =>
      api.post(`/sessions/${sessionId}/messages`, { content, role: "user" }, token),
  },

  agent: {
    chat: (token: string, sessionId: string, message: string, reelCount?: number) =>
      api.post<ChatResponse>(
        "/agent/chat",
        reelCount ? { session_id: sessionId, message, reel_count: reelCount } : { session_id: sessionId, message },
        token
      ),
    graph: () => api.get<GraphInfo>("/agent/graph"),
  },

  pipeline: {
    run: (token: string, stages?: string[]) => {
      const query = stages && stages.length
        ? `?${stages.map((s) => `stages=${encodeURIComponent(s)}`).join("&")}`
        : ""
      return api.post<PipelineRunResponse>(`/pipeline/run${query}`, undefined, token)
    },
    stages: () => api.get<PipelineStagesResponse>("/pipeline/stages"),
  },

  ingest: {
    account: (token: string, username: string, maxReels?: number) =>
      api.post<{ status: string; account: Account }>(
        "/ingest/account",
        maxReels ? { username, max_reels: maxReels } : { username },
        token
      ),
    getAccount: (token: string, username: string) =>
      api.get<Account>(`/ingest/account/${username}`, token),
    reels: (token: string, accountId: string) =>
      api.get<ReelsResponse>(`/ingest/account/${accountId}/reels`, token),
    reel: (token: string, reelId: string) =>
      api.get<ReelDetail>(`/ingest/reel/${reelId}`, token),
  },

  analytics: {
    summary: (token: string, limit?: number) =>
      api.get<AnalyticsSummary>(
        `/analytics/summary${limit ? `?limit=${limit}` : ""}`,
        token
      ),
  },

  content: {
    reels: (token: string, limit?: number) =>
      api.get<ContentReelsResponse>(
        `/content/reels${limit ? `?limit=${limit}` : ""}`,
        token
      ),
  },
}

export interface TopReel {
  id: string
  instagram_reel_id: string
  video_url: string | null
  views: number
  likes: number
  engagement_rate: number
  virality_score: number
  posted_at: string | null
  comments_count?: number
  saves?: number
  shares?: number
  caption?: string | null
}

export interface AnalyticsSummary {
  total_reels: number
  total_accounts: number
  avg_engagement_rate: number
  avg_virality_score: number
  total_views: number
  total_likes: number
  total_comments: number
  total_saves: number
  total_shares: number
  top_reels: TopReel[]
  reels: TopReel[]
}

export interface ApiHealth {
  status: string
  database: string
  version?: string
  reel_count?: number
  last_run?: string | null
  // Epoch seconds, or null if the stage has never run. `last_run` above is a
  // status label ("never_run", "success", ...), not a timestamp - it can't be
  // passed to a date formatter.
  last_run_timestamp?: number | null
  intelligence_count?: number
  profile_exists?: boolean
  scheduler?: string
  alerts?: string[]
}

export interface PipelineHealth {
  status: string
  pipeline: {
    scheduler_running: boolean
    consecutive_failures: number
    alert_threshold: number
  }
  stages: string[]
}

export interface PipelineRunResponse {
  pipeline_run_id: string
  status: string
  elapsed_sec: number
  stages: { name: string; status: string; elapsed_sec: number; error?: string }[]
  stages_order: string[]
}

export interface PipelineStagesResponse {
  stages: string[]
  description: Record<string, string>
}

export interface SessionsResponse {
  sessions: Session[]
  count: number
}

export interface Session {
  id: string
  userId: string
  summary?: string
  createdAt: string
  updatedAt: string
}

export interface MessagesResponse {
  messages: ChatMessage[]
  count: number
}

export interface ChatMessage {
  id?: string
  sessionId: string
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
  createdAt?: string
}

export interface Citation {
  source: string
  type: string
  summary: string
}

export interface ChatResponse {
  session_id: string
  response: string
  citations: Citation[]
  confidence_score: number
  intent: string
  evidence: Record<string, unknown>
  elapsed_sec: number
  transcription_status?: TranscriptionStatusItem[]
}

export interface TranscriptionStatusItem {
  reel_id: string
  instagram_reel_id?: string
  transcript?: string
  skipped?: boolean
  error?: string
}

export interface GraphInfo {
  nodes: string[]
  edges: { source: string; target: string; conditional: boolean }[]
}

export interface Account {
  id: string
  username: string
  instagramId?: string
  followerCount?: number
  followingCount?: number
  postsCount?: number
  isCompetitor?: boolean
  fullName?: string
  biography?: string
  profilePicUrl?: string
  isVerified?: boolean
  isPrivate?: boolean
  externalUrl?: string
}

export interface ReelsResponse {
  reels: Reel[]
  limit: number
  offset: number
  count: number
}

export interface Reel {
  id: string
  accountId: string
  instagramReelId: string
  videoUrl?: string
  caption?: string
  durationSec?: number
  postedAt: string
  viewCount?: number
  likeCount?: number
  commentsCount?: number
}

export interface ReelDetail extends Reel {
  transcript?: string
  visualTopics?: string[]
  textOverlays?: string[]
  visualSummary?: string
  metrics?: ReelMetrics
  intelligence?: ContentIntelligence
  // GET /ingest/reel/{instagram_reel_id} joins Reel + ReelMetric and returns
  // these flat on the row (not nested under `metrics`) - see
  // app/db.py::get_reel_by_instagram_id.
  views?: number
  likes?: number
  saves?: number
  shares?: number
  engagementRate?: number
  viralityScore?: number
  saveRate?: number
  shareRate?: number
  commentRate?: number
}

export interface ReelMetrics {
  views?: number
  likes?: number
  commentsCount?: number
  saves?: number
  shares?: number
  engagementRate?: number
  viralityScore?: number
}

export interface ContentIntelligence {
  topic?: string
  hookType?: string
  hookText?: string
  contentFormat?: string
  sentiment?: string
  audienceIntent?: string
}

export interface ContentReel {
  id: string
  instagram_reel_id: string
  video_url: string | null
  caption: string | null
  views: number
  likes: number
  comments_count: number
  engagement_rate: number
  virality_score: number
  topic: string | null
  hook_type: string | null
  hook_text: string | null
  cta: string | null
  content_format: string | null
  sentiment: string | null
  posted_at: string | null
}

export interface ContentReelsResponse {
  reels: ContentReel[]
  count: number
}
