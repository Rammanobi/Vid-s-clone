"use client"

export function PremiumLoadingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-3">
        {/* Bot Avatar */}
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 border border-blue-500/30 flex items-center justify-center">
          <div className="w-4 h-4 bg-white rounded-full opacity-80" />
        </div>

        {/* Loading Bubble */}
        <div className="bg-gradient-to-r from-secondary/50 to-secondary/30 backdrop-blur-sm border border-amber-600/20 rounded-3xl px-6 py-4 max-w-sm shadow-lg">
          <div className="space-y-3">
            {/* Typing dots */}
            <div className="flex gap-2 items-center">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0s" }} />
                <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }} />
                <div className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }} />
              </div>
              <span className="text-amber-400 font-medium text-sm ml-2">Reel Bot is thinking</span>
            </div>

            {/* Estimated time */}
            <p className="text-foreground/50 text-xs pl-7">Usually takes 2-3 seconds...</p>
          </div>
        </div>
      </div>
    </div>
  )
}
