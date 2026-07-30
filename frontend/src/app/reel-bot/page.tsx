"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Send, Loader2, Plus, CheckCircle2 } from "lucide-react"
import { api, type ReelBotIngestResponse } from "@/lib/api"
import { PromptChips } from "./components/PromptChips"
import { MessageBubble } from "./components/MessageBubble"
import { PremiumLoadingIndicator } from "./components/PremiumLoadingIndicator"

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
                <div className="p-6 bg-gradient-to-r from-green-600/10 to-emerald-600/5 border border-green-600/30 rounded-xl space-y-4 animate-fade-in shadow-lg">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-6 h-6 text-green-400" />
                    <div>
                      <p className="text-green-400 font-bold text-lg">Connected & Analyzed!</p>
                      <p className="text-foreground/70 text-sm">
                        Successfully analyzed {ingestResult.reels_synced} reels
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {ingestResult.avg_wpm && (
                      <div className="bg-secondary/40 border border-border/30 rounded-lg p-3">
                        <p className="text-foreground/60 text-xs font-medium">Average Speaking Speed</p>
                        <p className="text-xl font-bold text-amber-300 mt-1">{ingestResult.avg_wpm.toFixed(0)} WPM</p>
                      </div>
                    )}
                    <div className="bg-secondary/40 border border-border/30 rounded-lg p-3">
                      <p className="text-foreground/60 text-xs font-medium">Reels Analyzed</p>
                      <p className="text-xl font-bold text-green-400 mt-1">{ingestResult.reels_synced}</p>
                    </div>
                  </div>

                  {ingestResult.top_keywords.length > 0 && (
                    <div>
                      <p className="text-foreground/70 font-medium text-sm mb-2">Top Topics Discussed:</p>
                      <div className="flex flex-wrap gap-2">
                        {ingestResult.top_keywords.map((kw) => (
                          <Badge
                            key={kw}
                            className="bg-amber-600/30 text-amber-300 border-amber-600/50 font-medium"
                          >
                            {kw}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  <Button
                    onClick={() => setPhase("chat")}
                    className="w-full mt-2 bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white font-bold py-3 text-base shadow-lg hover:shadow-xl transition-all"
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
      <div className="border-b border-amber-600/20 bg-gradient-to-r from-secondary/40 to-transparent backdrop-blur-sm px-6 py-5 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-amber-600 to-amber-700 flex items-center justify-center shadow-lg">
              <span className="text-lg">🤖</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Reel Bot</h1>
              <div className="flex items-center gap-2 mt-1">
                <p className="text-sm text-foreground/70 font-medium">@{handle}</p>
                <div className="flex items-center gap-1 text-sm text-green-400">
                  <CheckCircle2 className="w-4 h-4" />
                  {ingestResult?.reels_synced || 0} reels analyzed
                </div>
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="text-foreground/60 hover:text-foreground hover:bg-amber-600/10 transition-all"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Account
          </Button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto w-full">
        <div className="w-full max-w-3xl mx-auto px-6 py-8 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="space-y-4">
                <div>
                  <h2 className="text-2xl font-bold text-foreground mb-2">
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

          {chatLoading && <PremiumLoadingIndicator />}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area - Fixed at Bottom */}
      <div className="w-full bg-gradient-to-t from-secondary/30 via-secondary/15 to-transparent px-6 py-8 flex-shrink-0 border-t border-border/20">
        <form onSubmit={handleSendMessage} className="w-full max-w-3xl mx-auto">
          <div className="relative flex items-end gap-3 bg-gradient-to-r from-secondary/60 to-secondary/40 backdrop-blur-sm border border-amber-600/30 rounded-3xl px-6 py-4 transition-all duration-200 hover:border-amber-600/50 hover:bg-gradient-to-r hover:from-secondary/70 hover:to-secondary/50 focus-within:border-amber-500/60 focus-within:ring-2 focus-within:ring-amber-500/30">
            {/* Textarea for growing input */}
            <textarea
              placeholder="Ask about your reels, engagement trends, content strategy..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={chatLoading}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSendMessage(input)
                }
              }}
              className="flex-1 bg-transparent text-foreground placeholder:text-foreground/50 text-base resize-none outline-none min-h-14 max-h-32 py-2 font-medium"
              rows={1}
            />

            {/* Send Button */}
            <Button
              type="submit"
              disabled={chatLoading || !input.trim()}
              className="flex-shrink-0 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white rounded-full p-3 transition-all duration-200 shadow-lg hover:shadow-2xl hover:scale-110 disabled:opacity-50 disabled:scale-100 h-12 w-12 flex items-center justify-center"
            >
              {chatLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
          <p className="text-xs text-foreground/40 mt-3 text-center">
            Press Enter to send • Shift+Enter for new line
          </p>
        </form>
      </div>
    </div>
  )
}
