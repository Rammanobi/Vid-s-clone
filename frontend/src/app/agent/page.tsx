"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { useAuth } from "@/lib/auth-context"
import { api, type ChatResponse, type TranscriptionStatusItem, type Session } from "@/lib/api"
import { Bot, Send, User, AlertCircle, Loader2, History, Plus, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRelativeTime } from "@/lib/utils"
import { getPersistent, setPersistent, clearPersistent } from "@/lib/cache"

const CHAT_SESSION_STORAGE_KEY = "agent_chat_session_id"

const suggestions = [
  "What's my best performing content?",
  "Which topics drive the most engagement?",
  "Analyze my content strategy",
  "What should I post next?",
]

export default function AgentPage() {
  const { token } = useAuth()
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; citations?: ChatResponse["citations"]; confidence?: number; transcriptionStatus?: TranscriptionStatusItem[] }[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [graphNodes, setGraphNodes] = useState<string[]>([])
  const [reelCount, setReelCount] = useState(1)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.agent.graph().then((g) => setGraphNodes(g.nodes)).catch(() => {})
  }, [])

  const loadSession = (token: string, id: string) =>
    api.session.messages(token, id).then((res) => {
      setSessionId(id)
      setPersistent(CHAT_SESSION_STORAGE_KEY, id)
      setMessages(
        res.messages.map((m) => ({
          role: m.role,
          content: m.content,
          citations: Array.isArray(m.citations) ? m.citations : [],
        }))
      )
    })

  // Chat sessions persist across browser restarts (unlike the transient
  // dashboard/analytics cache) - the backend keeps message history around,
  // so restore it instead of silently starting a new conversation on every
  // page visit.
  useEffect(() => {
    if (!token) return
    const storedSessionId = getPersistent(CHAT_SESSION_STORAGE_KEY)
    if (!storedSessionId) return

    loadSession(token, storedSessionId).catch(() => {
      // Session no longer exists server-side (404, etc.) - clear it and
      // fall back to starting fresh rather than getting stuck.
      clearPersistent(CHAT_SESSION_STORAGE_KEY)
    })
  }, [token])

  const openHistory = () => {
    setHistoryOpen((prev) => !prev)
    if (!token || sessions.length > 0) return
    setSessionsLoading(true)
    api.session
      .list(token)
      .then((res) => setSessions(res.sessions))
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false))
  }

  const selectSession = async (id: string) => {
    if (!token || id === sessionId) {
      setHistoryOpen(false)
      return
    }
    try {
      await loadSession(token, id)
    } finally {
      setHistoryOpen(false)
    }
  }

  const startNewChat = () => {
    clearPersistent(CHAT_SESSION_STORAGE_KEY)
    setSessionId(null)
    setMessages([])
    setHistoryOpen(false)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const sendMessage = async (message: string) => {
    if (!message.trim() || loading || !token) return

    setMessages((prev) => [...prev, { role: "user", content: message }])
    setInput("")
    setLoading(true)

    try {
      let sid = sessionId
      if (!sid) {
        const session = await api.session.create(token)
        sid = session.id
        setSessionId(sid)
        setPersistent(CHAT_SESSION_STORAGE_KEY, sid)
      }
      const result = await api.agent.chat(token, sid, message, reelCount)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.response,
          citations: result.citations,
          confidence: result.confidence_score,
          transcriptionStatus: result.transcription_status,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Request failed"}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[420px] flex-col space-y-4">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">AI Agent</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Ask questions about your content strategy
        </p>
      </div>

      {graphNodes.length > 0 && (
        <div className="flex flex-wrap gap-1.5 animate-fade-in stagger-1">
          {graphNodes.map((node) => (
            <Badge key={node} variant="outline" className="text-[10px]">
              {node}
            </Badge>
          ))}
        </div>
      )}

      <Card className="relative flex flex-1 flex-col overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="h-5 w-5" aria-hidden="true" />
            Chat
          </CardTitle>
          <div className="flex items-center gap-1.5">
            <Button variant="outline" size="sm" onClick={startNewChat}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              New chat
            </Button>
            <Button variant="outline" size="sm" onClick={openHistory} aria-expanded={historyOpen}>
              <History className="h-3.5 w-3.5" aria-hidden="true" />
              History
            </Button>
          </div>
        </CardHeader>

        {historyOpen && (
          <div className="absolute right-4 top-14 z-20 w-80 max-h-96 overflow-y-auto rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center justify-between border-b border-zinc-200 px-3 py-2 dark:border-zinc-800">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Past conversations
              </span>
              <button
                onClick={() => setHistoryOpen(false)}
                aria-label="Close history"
                className="text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-50"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {sessionsLoading ? (
              <p className="p-4 text-center text-sm text-zinc-400">Loading...</p>
            ) : sessions.length === 0 ? (
              <p className="p-4 text-center text-sm text-zinc-400">No past conversations yet</p>
            ) : (
              <ul>
                {sessions.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => selectSession(s.id)}
                      className={cn(
                        "flex w-full flex-col items-start gap-0.5 px-3 py-2.5 text-left text-sm transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900",
                        s.id === sessionId && "bg-zinc-100 dark:bg-zinc-800"
                      )}
                    >
                      <span className="truncate w-full font-medium">
                        {s.summary || `Conversation ${s.id.slice(0, 8)}`}
                      </span>
                      <span className="text-xs text-zinc-400">
                        {formatRelativeTime(s.updatedAt)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <CardContent className="flex flex-1 flex-col p-0">
          <div className="flex-1 overflow-y-auto overscroll-contain p-4 space-y-4" style={{ WebkitOverflowScrolling: "touch" }}>
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Bot className="mb-4 h-12 w-12 text-zinc-300 dark:text-zinc-600" />
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Ask me anything about your content strategy
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => sendMessage(s)}
                      className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  "flex animate-fade-in gap-3",
                  msg.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === "assistant" && (
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                    <Bot className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[80%] space-y-2 rounded-2xl px-4 py-2.5",
                    msg.role === "user"
                      ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                      : "bg-zinc-100 dark:bg-zinc-800"
                  )}
                >
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</div>
                  {Array.isArray(msg.citations) && msg.citations.length > 0 && (
                    <div className="border-t border-zinc-200/50 pt-2 dark:border-zinc-700/50">
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                        Sources
                      </p>
                      <div className="space-y-1">
                        {msg.citations.map((c, ci) => (
                          <p key={ci} className="text-[11px] text-zinc-500 dark:text-zinc-400">
                            <span className="font-medium">{c.source}</span> — {c.summary}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                  {msg.confidence !== undefined && (
                    <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
                      <div
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          msg.confidence > 0.7
                            ? "bg-emerald-500"
                            : msg.confidence > 0.4
                              ? "bg-amber-500"
                              : "bg-red-500"
                        )}
                      />
                      Confidence: {(msg.confidence * 100).toFixed(0)}%
                    </div>
                  )}
                  {msg.transcriptionStatus && msg.transcriptionStatus.length > 0 && (
                    <div className="space-y-0.5 border-t border-zinc-200/50 pt-2 dark:border-zinc-700/50">
                      {msg.transcriptionStatus.map((t, ti) => (
                        <p key={ti} className="text-[11px] text-zinc-400">
                          {t.error
                            ? `Failed: ${t.error}`
                            : t.skipped
                              ? "Reel already had a transcript, reused it"
                              : t.transcript
                                ? `Analyzed 1 reel (transcript: "${t.transcript.slice(0, 40)}${t.transcript.length > 40 ? "…" : ""}")`
                                : "Analyzed 1 reel"}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-900 dark:bg-zinc-50">
                    <User className="h-4 w-4 text-white dark:text-zinc-900" aria-hidden="true" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex animate-fade-in gap-3">
                <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                  <Bot className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                </div>
                <div className="flex items-center gap-2 rounded-2xl bg-zinc-100 px-4 py-2.5 dark:bg-zinc-800">
                  <Loader2 className="h-5 w-5 shrink-0 animate-spin text-zinc-400" />
                  {reelCount > 0 && (
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      Transcribing {reelCount} reel{reelCount > 1 ? "s" : ""} with Whisper, then answering...
                    </span>
                  )}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
            <div className="mb-3 flex items-center gap-2">
              <Select
                label="Reels to analyze"
                value={String(reelCount)}
                onChange={(e) => setReelCount(Number(e.target.value))}
                disabled={loading}
                className="h-9 w-auto"
                options={Array.from({ length: 5 }, (_, i) => {
                  const n = i + 1
                  return { value: String(n), label: `${n} reel${n > 1 ? "s" : ""}` }
                })}
              />
            </div>
            <p className="mb-3 text-xs text-zinc-400">
              Downloads and transcribes the reel&apos;s audio with Whisper before answering - takes a
              few seconds per reel.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                sendMessage(input)
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message..."
                disabled={loading || !token}
                className="flex-1 rounded-lg border border-zinc-200 bg-white px-4 py-2.5 text-sm focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400/20 dark:border-zinc-800 dark:bg-zinc-950 disabled:opacity-50"
                aria-label="Chat message"
              />
              <Button type="submit" size="icon" disabled={loading || !input.trim() || !token}>
                <Send className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Send message</span>
              </Button>
            </form>
            {!token && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-500">
                <AlertCircle className="h-3 w-3" />
                Sign in to use the AI agent
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
