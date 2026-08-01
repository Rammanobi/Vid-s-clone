"use client"

import { useState } from "react"
import { Copy, ThumbsUp, ThumbsDown, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"

interface MessageActionsProps {
  content: string
  onCopy?: () => void
}

export function MessageActions({ content, onCopy }: MessageActionsProps) {
  const [copied, setCopied] = useState(false)
  const [reactions, setReactions] = useState<{ [key: string]: boolean }>({
    like: false,
    dislike: false,
    fire: false,
  })

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    onCopy?.()
    setTimeout(() => setCopied(false), 2000)
  }

  const handleReaction = (reaction: string) => {
    setReactions((prev) => ({
      ...prev,
      [reaction]: !prev[reaction],
    }))
  }

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/20">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleCopy}
        className="h-8 w-8 p-0 hover:bg-amber-600/20 text-foreground/60 hover:text-amber-400"
        title="Copy message"
      >
        <Copy className="w-4 h-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleReaction("like")}
        className={`h-8 w-8 p-0 text-foreground/60 ${reactions.like ? "text-green-400 bg-green-600/20" : "hover:bg-green-600/10"}`}
        title="Helpful"
      >
        <ThumbsUp className="w-4 h-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleReaction("dislike")}
        className={`h-8 w-8 p-0 text-foreground/60 ${reactions.dislike ? "text-red-400 bg-red-600/20" : "hover:bg-red-600/10"}`}
        title="Not helpful"
      >
        <ThumbsDown className="w-4 h-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleReaction("fire")}
        className={`h-8 w-8 p-0 text-foreground/60 ${reactions.fire ? "text-orange-400 bg-orange-600/20" : "hover:bg-orange-600/10"}`}
        title="Amazing insight"
      >
        <Zap className="w-4 h-4" />
      </Button>

      {copied && (
        <span className="text-xs text-green-400 ml-auto">
          Copied!
        </span>
      )}
    </div>
  )
}
