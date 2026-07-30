import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ChevronRight } from "lucide-react"

interface PromptChipsProps {
  suggestions: string[]
  onSelect: (suggestion: string) => void
  disabled?: boolean
}

export function PromptChips({
  suggestions,
  onSelect,
  disabled,
}: PromptChipsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
      {suggestions.map((suggestion, idx) => (
        <Button
          key={idx}
          variant="outline"
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className={cn(
            "justify-start h-auto py-3 px-4 text-left text-sm font-medium",
            "bg-gradient-to-r from-secondary/40 to-secondary/20 border border-amber-600/30",
            "text-foreground/90 hover:text-foreground",
            "hover:bg-gradient-to-r hover:from-amber-600/20 hover:to-amber-600/10 hover:border-amber-600/50",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-all duration-200 hover:scale-105 hover:shadow-lg",
            "group"
          )}
        >
          <ChevronRight className="w-4 h-4 mr-2 text-amber-400 group-hover:translate-x-1 transition-transform" />
          <span>{suggestion}</span>
        </Button>
      ))}
    </div>
  )
}
