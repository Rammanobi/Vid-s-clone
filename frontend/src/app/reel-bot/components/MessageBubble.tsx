import { User, Bot } from "lucide-react"
import { cn } from "@/lib/utils"

interface MessageBubbleProps {
  role: "user" | "assistant"
  content: string
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user"

  return (
    <div
      className={cn(
        "flex gap-3 animate-fade-in",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary/50 border border-border/30 flex items-center justify-center">
          <Bot className="w-4 h-4 text-amber-600/60" />
        </div>
      )}

      <div
        className={cn(
          "max-w-md md:max-w-xl px-4 py-3 rounded-lg",
          isUser
            ? "bg-amber-600/20 border border-amber-600/30 text-foreground"
            : "bg-secondary/50 border border-border/30 text-foreground"
        )}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {content}
        </p>
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary/50 border border-border/30 flex items-center justify-center">
          <User className="w-4 h-4 text-foreground/60" />
        </div>
      )}
    </div>
  )
}
