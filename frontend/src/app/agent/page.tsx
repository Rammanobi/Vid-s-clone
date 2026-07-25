"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/lib/auth-context"
import { api, type ChatResponse } from "@/lib/api"
import { Bot, Send, User, AlertCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

const suggestions = [
  "What's my best performing content?",
  "Which topics drive the most engagement?",
  "Analyze my content strategy",
  "What should I post next?",
]

export default function AgentPage() {
  const { token } = useAuth()
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; citations?: ChatResponse["citations"]; confidence?: number }[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [graphNodes, setGraphNodes] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.agent.graph().then((g) => setGraphNodes(g.nodes)).catch(() => {})
  }, [])

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
      }
      const result = await api.agent.chat(token, sid, message)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.response,
          citations: result.citations,
          confidence: result.confidence_score,
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
    <div className="flex h-[calc(100vh-12rem)] flex-col space-y-4">
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

      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardHeader className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="h-5 w-5" aria-hidden="true" />
            Chat
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col p-0">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
                  {msg.citations && msg.citations.length > 0 && (
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
                <div className="rounded-2xl bg-zinc-100 px-4 py-2.5 dark:bg-zinc-800">
                  <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
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
