"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Send, Loader2, Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import { api, type ReelBotIngestResponse } from "@/lib/api"
import { PromptChips } from "./components/PromptChips"
import { MessageBubble } from "./components/MessageBubble"

type Phase = "ingestion" | "chat"
type IngestPhase = "idle" | "fetching" | "downloading" | "transcribing" | "processing"

interface Message {
  role: "user" | "assistant"
  content: string
}

type IngestResult = ReelBotIngestResponse

const DEFAULT_SUGGESTIONS = [
  "Which of my reels had the highest engagement?",
  "What topics do I talk about most?",
  "Am I speaking too fast or too slow?",
  "What makes my top reel successful?",
  "How has my performance changed recently?",
]

const INGEST_MESSAGES: Record<IngestPhase, string> = {
  idle: "Ready to connect...",
  fetching: "🔍 Fetching your Instagram profile...",
  downloading: "📥 Downloading your latest reels...",
  transcribing: "🎙️ Transcribing audio with AI...",
  processing: "⚙️ Analyzing and processing data...",
}

export default function ReelBotPage() {
  const [phase, setPhase] = useState<Phase>("ingestion")
  const [handle, setHandle] = useState("")
  const [handleInput, setHandleInput] = useState("")
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestPhase, setIngestPhase] = useState<IngestPhase>("idle")
  const [ingestError, setIngestError] = useState<string | null>(null)
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const [chatPhase, setChatPhase] = useState("")
  const [sessionId, setSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, chatLoading])

  useEffect(() => {
    if (!ingestLoading) return

    const phases: IngestPhase[] = ["fetching", "downloading", "transcribing", "processing"]
    let currentPhaseIndex = 0

    const interval = setInterval(() => {
      if (currentPhaseIndex < phases.length) {
        setIngestPhase(phases[currentPhaseIndex])
        currentPhaseIndex++
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [ingestLoading])

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault()
    setIngestError(null)
    setIngestPhase("fetching")

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
      setIngestPhase("idle")
      setPhase("chat")
      setSessionId(null)
      setMessages([])
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Connection error")
      setIngestPhase("idle")
    } finally {
      setIngestLoading(false)
    }
  }

  const handleSendMessage = async (e: React.FormEvent | string) => {
    const message = typeof e === "string" ? e : input

    if (typeof e !== "string") {
      e.preventDefault()
    }

    if (!message.trim() || chatLoading || !handle) return

    const userMessage: Message = { role: "user", content: message }
    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setChatLoading(true)

    try {
      const result = await api.reelBot.chat({
        instagram_handle: handle,
        session_id: sessionId,
        message: message,
      })
      setSessionId(result.session_id)

      const assistantMessage: Message = {
        role: "assistant",
        content: result.response,
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to get response"
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${errorMsg}` },
      ])
    } finally {
      setChatLoading(false)
    }
  }

  const handleReset = () => {
    setPhase("ingestion")
    setHandle("")
    setHandleInput("")
    setIngestResult(null)
    setMessages([])
    setSessionId(null)
    setIngestError(null)
  }

  if (phase === "ingestion") {
    return (
      <div className="w-full max-w-2xl mx-auto py-12 px-4">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2 text-foreground">Reel Bot</h1>
          <p className="text-foreground/60">
            Analyze your Instagram Reels with AI-powered insights
          </p>
        </div>

        <Card className="border-border/50 bg-secondary/5">
          <CardHeader>
            <CardTitle className="text-xl">Connect Your Account</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Instagram Handle
                </label>
                <div className="flex gap-2">
                  <Input
                    type="text"
                    placeholder="@username"
                    value={handleInput}
                    onChange={(e) => setHandleInput(e.target.value)}
                    disabled={ingestLoading}
                    className="flex-1 bg-secondary/50 border-border/30 text-foreground placeholder:text-foreground/40"
                  />
                  <Button
                    type="submit"
                    disabled={ingestLoading}
                    className="bg-amber-600/80 hover:bg-amber-600 text-white"
                  >
                    {ingestLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      "Connect"
                    )}
                  </Button>
                </div>
                <p className="text-xs text-foreground/50 mt-2">
                  We analyze the last 20 public reels from your account
                </p>
              </div>

              {ingestLoading && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-amber-400 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                      <div className="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                    </div>
                    <span className="text-amber-400 font-medium text-sm">
                      {INGEST_MESSAGES[ingestPhase]}
                    </span>
                  </div>
                  <div className="h-1 bg-secondary/30 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-500/60 rounded-full w-3/4 animate-pulse" />
                  </div>
                </div>
              )}

              {ingestError && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
                  {ingestError}
                </div>
              )}

              {ingestResult && (
                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded space-y-3 animate-fade-in">
                  <div>
                    <p className="text-green-400 font-medium">✓ Connected!</p>
                    <p className="text-foreground/70 text-sm mt-1">
                      {ingestResult.reels_synced} reels analyzed
                    </p>
                  </div>

                  {ingestResult.avg_wpm && (
                    <div className="text-sm text-foreground/60">
                      <span className="font-medium">Avg WPM:</span>{" "}
                      {ingestResult.avg_wpm.toFixed(0)} words/min
                    </div>
                  )}

                  {ingestResult.top_keywords.length > 0 && (
                    <div className="text-sm text-foreground/60">
                      <span className="font-medium">Top Topics:</span>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {ingestResult.top_keywords.map((kw) => (
                          <Badge
                            key={kw}
                            variant="secondary"
                            className="bg-amber-600/20 text-amber-300 border-amber-600/30"
                          >
                            {kw}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  <Button
                    onClick={() => setPhase("chat")}
                    className="w-full mt-4 bg-amber-600/80 hover:bg-amber-600 text-white"
                  >
                    Start Chatting
                  </Button>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-foreground/40 text-xs mt-8">
          No login required. We only analyze public data.
        </p>
      </div>
    )
  }

  return (
    <div className="w-full h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="border-b border-border/30 bg-secondary/5 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Reel Bot</h1>
            <p className="text-xs text-foreground/50">
              @{handle} • {ingestResult?.reels_synced || 0} reels analyzed
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-foreground/60 hover:text-foreground"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Account
          </Button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="space-y-4">
                <div>
                  <h2 className="text-xl font-semibold text-foreground mb-2">
                    Ask about your reels
                  </h2>
                  <p className="text-foreground/60 text-sm">
                    Get insights about your content performance and strategy
                  </p>
                </div>

                <PromptChips
                  suggestions={DEFAULT_SUGGESTIONS}
                  onSelect={handleSendMessage}
                  disabled={chatLoading}
                />
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <MessageBubble
                key={idx}
                role={msg.role}
                content={msg.content}
              />
            ))
          )}

          {chatLoading && (
            <div className="flex justify-start">
              <div className="bg-gradient-to-r from-secondary/70 to-secondary/50 border border-border/40 rounded-2xl px-5 py-4 max-w-sm shadow-sm">
                <div className="space-y-2">
                  <div className="flex gap-2 items-center">
                    <div className="flex gap-1">
                      <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" />
                      <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                      <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                    </div>
                    <span className="text-amber-400 font-medium text-sm">Analyzing your reels...</span>
                  </div>
                  <p className="text-foreground/60 text-xs pl-9">This may take a moment as we review your content</p>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-border/30 bg-gradient-to-t from-secondary/10 to-transparent px-4 py-6">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSendMessage} className="flex gap-3">
            <Input
              type="text"
              placeholder="Ask about your reels, content strategy, or performance..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={chatLoading}
              className="flex-1 bg-secondary/60 border border-border/40 text-foreground placeholder:text-foreground/50 rounded-2xl px-5 py-3 text-base focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/50"
            />
            <Button
              type="submit"
              disabled={chatLoading || !input.trim()}
              className="bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white px-6 py-3 rounded-2xl font-medium transition-all shadow-lg hover:shadow-xl disabled:opacity-50"
            >
              {chatLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Send className="w-5 h-5" />
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
