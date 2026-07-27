"use client"

import { type SelectHTMLAttributes, forwardRef } from "react"
import { cn } from "@/lib/utils"

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, options, id, placeholder, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, "-")

    // Filter out attributes that might be added by external scripts/extensions
    const filteredProps = Object.fromEntries(
      Object.entries(props).filter(([key]) => !key.startsWith('fdprocessedid'))
    )

    return (
      <div className="space-y-2">
        {label && (
          <label htmlFor={selectId} className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            {label}
          </label>
        )}
        <select
          id={selectId}
          className={cn(
            "flex h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-950 dark:ring-offset-zinc-950 dark:focus-visible:ring-zinc-600",
            error && "border-red-500",
            className
          )}
          ref={ref}
          aria-invalid={!!error}
          suppressHydrationWarning
          {...filteredProps}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-red-500" role="alert">{error}</p>}
      </div>
    )
  }
)
Select.displayName = "Select"

export { Select }
