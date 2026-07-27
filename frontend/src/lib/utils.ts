import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toLocaleString()
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

// Backend timestamps (e.g. `last_run_timestamp`) come from Python's
// time.time() - epoch SECONDS, not JS's epoch milliseconds. A number below
// this many digits can't be a millisecond timestamp in this century, so
// treat it as seconds and scale up. ISO strings and Date objects pass through.
function toJsDate(date: string | number | Date): Date {
  if (typeof date === "number" && date < 1e12) {
    return new Date(date * 1000)
  }
  return new Date(date)
}

export function formatDate(date: string | number | Date): string {
  const d = toJsDate(date)
  if (Number.isNaN(d.getTime())) return "—"
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(d)
}

export function formatRelativeTime(date: string | number | Date): string {
  const d = toJsDate(date)
  if (Number.isNaN(d.getTime())) return "—"
  const diff = Date.now() - d.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  return formatDate(date)
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "success":
    case "healthy":
      return "text-emerald-500"
    case "partial":
    case "degraded":
      return "text-amber-500"
    case "failed":
    case "error":
      return "text-red-500"
    case "running":
    case "pending":
      return "text-blue-500"
    case "skipped":
      return "text-zinc-400"
    default:
      return "text-zinc-500"
  }
}

export function getStatusBg(status: string): string {
  switch (status) {
    case "success":
    case "healthy":
      return "bg-emerald-500/10 border-emerald-500/20"
    case "partial":
    case "degraded":
      return "bg-amber-500/10 border-amber-500/20"
    case "failed":
    case "error":
      return "bg-red-500/10 border-red-500/20"
    case "running":
    case "pending":
      return "bg-blue-500/10 border-blue-500/20"
    case "skipped":
      return "bg-zinc-500/10 border-zinc-500/20"
    default:
      return "bg-zinc-500/5 border-zinc-500/10"
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + "..."
}
