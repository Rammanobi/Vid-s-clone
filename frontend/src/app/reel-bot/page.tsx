"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import {
  AtSign,
  Lock,
  Loader2,
  Menu,
  Plus,
  Paperclip,
  ArrowUp,
  TrendingUp,
  BarChart3,
  ArrowLeftRight,
  Lightbulb,
  User,
} from "lucide-react"
import {
  api,
  type ReelBotIngestResponse,
  type ReelBotSessionSummary,
} from "@/lib/api"
import { RichTextResponse } from "./components/RichTextResponse"

type Phase = "connect" | "chat"

interface Message {
  role: "user" | "assistant"
  content: string
}

const SUGGESTIONS = [
  { icon: TrendingUp, label: "Best performing reel", prompt: "What is my best performing reel this month?" },
  { icon: BarChart3, label: "Engagement drop analysis", prompt: "Analyze the engagement drop last week" },
  { icon: ArrowLeftRight, label: "Benchmark vs top creators", prompt: "Compare my last 5 reels vs top creators" },
  { icon: Lightbulb, label: "Hook ideas for tech", prompt: "Generate hook ideas for tech reviews" },
]

function TypingDots() {
  return (
    <div className="flex w-full justify-start">
      <div className="bg-[#f9f9f9] border border-[#cfc4c5] rounded-2xl rounded-tl-sm shadow-sm px-5 py-4 flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 bg-[#7e7576] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
        <div className="w-1.5 h-1.5 bg-[#7e7576] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
        <div className="w-1.5 h-1.5 bg-[#7e7576] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  )
}

export default function ReelBotPage() {
  const [phase, setPhase] = useState<Phase>("connect")
  const [handle, setHandle] = useState("")
  const [handleInput, setHandleInput] = useState("")
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestError, setIngestError] = useState<string | null>(null)
  const [ingestResult, setIngestResult] = useState<ReelBotIngestResponse | null>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sessions, setSessions] = useState<ReelBotSessionSummary[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, chatLoading])

  const refreshSessions = useCallback(async (h: string) => {
    try {
      const res = await api.reelBot.sessions(h)
      setSessions(res.sessions)
    } catch {
      // Sidebar history is a nice-to-have - a failure here shouldn't block chat.
    }
  }, [])

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault()
    setIngestError(null)

    const cleanHandle = handleInput.toLowerCase().replace(/^@/, "").trim()
    if (!cleanHandle) {
      setIngestError("Please enter an Instagram handle")
      return
    }

    setIngestLoading(true)
    try {
      const result = await api.reelBot.ingest({ instagram_handle: cleanHandle })
      setIngestResult(result)
      setHandle(result.instagram_handle)
      setPhase("chat")
      setSessionId(null)
      setMessages([])
      refreshSessions(result.instagram_handle)
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Connection error")
    } finally {
      setIngestLoading(false)
    }
  }

  const sendMessage = async (text: string) => {
    if (!text.trim() || chatLoading || !handle) return

    const isFirstMessageOfSession = sessionId === null
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setInput("")
    if (textareaRef.current) textareaRef.current.style.height = "40px"
    setChatLoading(true)

    try {
      const result = await api.reelBot.chat({
        instagram_handle: handle,
        session_id: sessionId,
        message: text,
      })
      setSessionId(result.session_id)
      setMessages((prev) => [...prev, { role: "assistant", content: result.response }])
      if (isFirstMessageOfSession) refreshSessions(handle)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to get response"
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${errorMsg}` }])
    } finally {
      setChatLoading(false)
    }
  }

  const handleNewChat = () => {
    setSessionId(null)
    setMessages([])
  }

  const handleNewAccount = () => {
    setPhase("connect")
    setHandle("")
    setHandleInput("")
    setIngestResult(null)
    setMessages([])
    setSessionId(null)
    setSessions([])
    setIngestError(null)
  }

  const openPastSession = async (s: ReelBotSessionSummary) => {
    try {
      const res = await api.reelBot.sessionMessages(s.session_id)
      setMessages(res.messages as Message[])
      setSessionId(res.session_id)
    } catch {
      // Leave current chat untouched if a past session can't be loaded.
    }
  }

  // ---------------------------------------------------------------------
  // Connect screen
  // ---------------------------------------------------------------------
  if (phase === "connect") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f9f9f9] p-6">
        <div className="w-full max-w-[420px] bg-white p-10 rounded-xl border border-[#cfc4c5] shadow-sm flex flex-col items-center text-center">
          <div className="w-24 h-24 mb-6 rounded-full bg-[#f3f3f4] border border-[#cfc4c5] flex items-center justify-center overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/reel-bot/logo.png" alt="Reel Bot" className="w-16 h-16 object-contain" />
          </div>
          <h1 className="text-[36px] leading-[44px] font-semibold tracking-tight text-[#1a1c1c] mb-2">
            Reel Bot
          </h1>
          <p className="text-base text-[#4c4546] mb-8 max-w-[280px]">
            Analyze your Instagram Reels with AI-powered insights.
          </p>

          <form onSubmit={handleConnect} className="w-full flex flex-col gap-4">
            <div className="relative w-full">
              <AtSign className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#4c4546]" />
              <input
                type="text"
                placeholder="username"
                value={handleInput}
                onChange={(e) => setHandleInput(e.target.value)}
                disabled={ingestLoading}
                className="w-full bg-white border border-[#cfc4c5] rounded-lg py-2 pr-4 pl-10 text-sm text-[#1a1c1c] placeholder-[#9CA3AF] focus:outline-none focus:border-black transition-colors h-[44px]"
              />
            </div>
            <button
              type="submit"
              disabled={ingestLoading}
              className="w-full bg-black text-white text-xs font-medium tracking-wide py-2 px-4 rounded-lg h-[44px] hover:bg-black/90 transition-all flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {ingestLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Fetching your reels...
                </>
              ) : (
                "Connect"
              )}
            </button>
          </form>

          {ingestError && (
            <div className="mt-4 w-full p-3 bg-[#fbe9e7] border border-[#ba1a1a]/30 rounded-lg text-[#ba1a1a] text-sm">
              {ingestError}
            </div>
          )}

          <div className="mt-6 flex items-center gap-1.5 text-[#4c4546]/70 text-xs">
            <Lock className="w-4 h-4" />
            <span>Secure read-only access</span>
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------
  // Chat dashboard
  // ---------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-white flex">
      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen bg-white border-r border-[#cfc4c5] flex flex-col z-20 transition-[width] duration-200 ${
          sidebarOpen ? "w-[260px]" : "w-[56px]"
        }`}
      >
        <div className="h-16 flex items-center px-4 border-b border-[#cfc4c5] justify-between">
          {sidebarOpen && (
            <div className="flex items-center gap-2 overflow-hidden whitespace-nowrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/reel-bot/logo.png" alt="Reel Bot" className="h-6 w-6 flex-shrink-0 object-contain" />
              <span className="text-lg font-semibold tracking-tight text-[#1a1c1c]">Reel Bot</span>
            </div>
          )}
          <button
            className="p-1.5 hover:bg-[#e8e8e8] rounded-full flex-shrink-0"
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Toggle sidebar"
          >
            <Menu className="w-5 h-5 text-[#1a1c1c]" />
          </button>
        </div>

        <div className="p-2">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 p-2 border border-[#cfc4c5] rounded-lg hover:bg-[#f3f3f4] transition-colors text-[#1a1c1c]"
          >
            <Plus className="w-4 h-4 flex-shrink-0" />
            {sidebarOpen && <span className="text-xs font-medium">New Chat</span>}
          </button>
        </div>

        {sidebarOpen && (
          <div className="flex-1 overflow-y-auto px-2 flex flex-col gap-1 reel-bot-scrollbar">
            <span className="px-2 py-1 text-[11px] text-[#4c4546] font-medium uppercase tracking-wider">
              History
            </span>
            {sessions.length === 0 ? (
              <p className="px-2 py-1 text-xs text-[#4c4546]/70">No past conversations yet</p>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => openPastSession(s)}
                  className={`text-left p-2 rounded-lg hover:bg-[#f3f3f4] flex flex-col gap-0.5 transition-colors ${
                    s.session_id === sessionId ? "bg-[#f3f3f4]" : ""
                  }`}
                >
                  <span className="text-sm text-[#1a1c1c] truncate">{s.preview}</span>
                  <span className="text-[11px] text-[#4c4546]">
                    {new Date(s.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        <div className="p-2 border-t border-[#cfc4c5] mt-auto">
          <div className="flex items-center gap-2 p-2">
            <div className="w-8 h-8 rounded-full bg-black flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-white" />
            </div>
            {sidebarOpen && (
              <div className="flex flex-col min-w-0 overflow-hidden">
                <span className="text-sm font-bold truncate text-[#1a1c1c]">@{handle}</span>
                <span className="text-[10px] text-[#1a1c1c] px-1.5 py-0.5 bg-[#e8e8e8] border border-[#cfc4c5] rounded w-fit">
                  {ingestResult?.reels_synced ?? 0} reels analyzed
                </span>
              </div>
            )}
          </div>
          {sidebarOpen && (
            <button
              onClick={handleNewAccount}
              className="px-2 py-1 text-xs text-[#4c4546] hover:text-[#1a1c1c] transition-colors mt-1"
            >
              New Account
            </button>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className={`flex-1 flex flex-col min-h-screen transition-[padding] duration-200 ${sidebarOpen ? "pl-[260px]" : "pl-[56px]"}`}>
        <header className="h-16 flex items-center px-6 border-b border-[#cfc4c5] flex-shrink-0 sticky top-0 bg-white z-10">
          <span className="text-sm font-bold text-[#1a1c1c]">@{handle}</span>
          <span className="mx-2 text-[#7e7576]">·</span>
          <span className="text-sm text-[#4c4546]">{ingestResult?.reels_synced ?? 0} reels analyzed</span>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-10 flex flex-col gap-6 w-full max-w-3xl mx-auto pb-32 reel-bot-scrollbar">
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-[#f9f9f9] flex items-center justify-center mb-6 border border-[#cfc4c5] shadow-sm">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/reel-bot/logo.png" alt="Reel Bot" className="w-8 h-8 object-contain" />
              </div>
              <h1 className="text-[28px] leading-[36px] font-semibold text-[#1a1c1c] mb-2 tracking-tight">
                Reel Analysis AI
              </h1>
              <p className="text-base text-[#4c4546] max-w-md mb-8">
                I&apos;m ready to analyze your recent performance, engagement trends, and content strategy. What
                would you like to know?
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-2xl">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => sendMessage(s.prompt)}
                    className="px-4 py-2 bg-[#f9f9f9] rounded-full border border-[#cfc4c5] hover:border-black hover:bg-[#f3f3f4] transition-all flex items-center gap-2 text-sm font-medium text-[#1a1c1c]"
                  >
                    <s.icon className="w-4 h-4 text-[#4c4546]" />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div key={idx} className={`flex w-full ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "user" ? (
                  <div className="max-w-[80%] bg-[#eeeeee] py-3 px-5 rounded-2xl rounded-tr-sm text-[#1a1c1c] text-base">
                    {m.content}
                  </div>
                ) : (
                  <div className="max-w-[85%] bg-[#f9f9f9] border border-[#cfc4c5] py-3 px-5 rounded-2xl rounded-tl-sm shadow-sm">
                    <RichTextResponse content={m.content} theme="mono" />
                  </div>
                )}
              </div>
            ))
          )}
          {chatLoading && <TypingDots />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          className={`fixed bottom-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-8 pb-6 px-6 transition-[left] duration-200 ${
            sidebarOpen ? "left-[260px]" : "left-[56px]"
          }`}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault()
              sendMessage(input)
            }}
            className="max-w-3xl mx-auto"
          >
            <div className="bg-[#f9f9f9] rounded-xl border border-[#cfc4c5] flex items-end p-2 shadow-sm focus-within:border-black transition-all">
              <button type="button" className="p-2 text-[#4c4546] hover:text-black transition-colors rounded-lg flex-shrink-0" title="Attach data (coming soon)" disabled>
                <Paperclip className="w-5 h-5" />
              </button>
              <textarea
                ref={textareaRef}
                placeholder="Ask about your reels..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={chatLoading}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = ""
                  el.style.height = `${el.scrollHeight}px`
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage(input)
                  }
                }}
                className="w-full bg-transparent border-none focus:ring-0 resize-none text-base text-[#1a1c1c] placeholder-[#9CA3AF] py-2 px-2 max-h-32 min-h-[40px] outline-none"
                rows={1}
              />
              <button
                type="submit"
                disabled={chatLoading || !input.trim()}
                className="bg-black text-white p-2 rounded-lg hover:bg-[#333] transition-colors flex-shrink-0 flex items-center justify-center shadow-sm ml-2 disabled:opacity-40 h-9 w-9"
              >
                {chatLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowUp className="w-5 h-5" />}
              </button>
            </div>
            <p className="text-center mt-2 text-[10px] text-[#4c4546] tracking-wide uppercase">
              Reel Bot may produce inaccurate information about real-time metrics.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
