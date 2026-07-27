import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

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
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full max-w-md">
      {suggestions.map((suggestion, idx) => (
        <Button
          key={idx}
          variant="outline"
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className={cn(
            "justify-start h-auto py-2 px-3 text-left text-sm",
            "bg-secondary/30 border-border/30 text-foreground/80",
            "hover:bg-secondary/50 hover:text-foreground hover:border-border/50",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors"
          )}
        >
          <span className="text-amber-600/60 mr-2">→</span>
          {suggestion}
        </Button>
      ))}
    </div>
  )
}
