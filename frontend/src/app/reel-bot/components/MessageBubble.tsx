import { User, Bot } from "lucide-react"
import { cn } from "@/lib/utils"
import { RichTextResponse } from "./RichTextResponse"
import { MessageActions } from "./MessageActions"
import { useState } from "react"

interface MessageBubbleProps {
  role: "user" | "assistant"
  content: string
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user"
  const [showActions, setShowActions] = useState(false)
  const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  return (
    <div
      className={cn(
        "flex gap-4 animate-fade-in group",
        isUser ? "justify-end" : "justify-start"
      )}
      onMouseEnter={() => !isUser && setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 border border-blue-500/30 flex items-center justify-center shadow-lg">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}

      <div className={cn("flex flex-col gap-1 max-w-2xl", isUser && "items-end")}>
        {/* Label */}
        <div className={cn("text-xs font-medium text-foreground/50 px-2", isUser && "text-right")}>
          {isUser ? "You" : "Reel Bot"}
        </div>

        {/* Message bubble */}
        <div
          className={cn(
            "rounded-3xl shadow-lg transition-all duration-200",
            isUser
              ? "bg-gradient-to-r from-amber-600 to-amber-700 text-white px-6 py-4 hover:shadow-xl hover:scale-105"
              : "bg-gradient-to-r from-secondary/50 to-secondary/30 backdrop-blur-sm border border-amber-600/20 text-foreground px-6 py-4"
          )}
        >
          <div className="text-sm leading-relaxed">
            {isUser ? (
              <p className="whitespace-pre-wrap break-words">{content}</p>
            ) : (
              <RichTextResponse content={content} />
            )}
          </div>
        </div>

        {/* Actions for assistant messages */}
        {!isUser && showActions && (
          <div className="mt-1 px-2">
            <MessageActions content={content} />
          </div>
        )}

        {/* Timestamp */}
        <div className={cn("text-xs text-foreground/40 px-2 mt-1", isUser && "text-right")}>
          {timestamp}
        </div>
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-r from-amber-600 to-amber-700 border border-amber-500/30 flex items-center justify-center shadow-lg">
          <User className="w-4 h-4 text-white" />
        </div>
      )}
    </div>
  )
}
