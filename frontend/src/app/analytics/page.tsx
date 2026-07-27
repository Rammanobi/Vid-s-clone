"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/lib/auth-context"
import { api, type AnalyticsSummary } from "@/lib/api"
import { formatNumber } from "@/lib/utils"
import { getCached, setCached } from "@/lib/cache"
import { BarChart3, Eye, ThumbsUp, MessageCircle, Bookmark, Share2, TrendingUp, AtSign } from "lucide-react"

const ANALYTICS_CACHE_KEY = "analytics_summary_cache"
const ANALYTICS_CACHE_TTL_MS = 60_000
const REEL_COUNT_OPTIONS = [5, 10, 20, 30] as const

export default function AnalyticsPage() {
  const { token } = useAuth()
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState<number>(10)

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    setLoading(true)

    // Show cached data immediately (if fresh) to skip the loading skeleton,
    // then always still fetch a fresh copy in the background below. Cache is
    // keyed to the default limit only, so it's skipped once the user picks a
    // different reel count.
    const cached =
      limit === 10
        ? getCached<AnalyticsSummary>(ANALYTICS_CACHE_KEY, ANALYTICS_CACHE_TTL_MS)
        : null
    if (cached) {
      setSummary(cached)
      setLoading(false)
    }

    api.analytics
      .summary(token, limit)
      .then((result) => {
        setSummary(result)
        if (limit === 10) setCached(ANALYTICS_CACHE_KEY, result)
      })
      .catch(() => {
        if (!cached) setSummary(null)
      })
      .finally(() => setLoading(false))
  }, [token, limit])

  const hasData = (summary?.total_reels ?? 0) > 0

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Performance metrics and engagement analysis
        </p>
      </div>

      {!loading && !hasData && (
        <Card className="animate-fade-in border-zinc-900 bg-zinc-900 text-white dark:border-zinc-50 dark:bg-zinc-50 dark:text-zinc-900">
          <CardContent className="flex flex-col items-start justify-between gap-4 p-6 sm:flex-row sm:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-white/10 p-2.5 dark:bg-zinc-900/10">
                <AtSign className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <p className="font-medium">No reel data yet</p>
                <p className="text-sm text-zinc-300 dark:text-zinc-600">
                  Connect an Instagram account to see real engagement numbers here
                </p>
              </div>
            </div>
            <Link
              href="/connect"
              className="shrink-0 rounded-lg bg-white/10 px-4 py-2 text-sm font-medium transition-colors hover:bg-white/20 dark:bg-zinc-900/10 dark:hover:bg-zinc-900/20"
            >
              Connect Account
            </Link>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard icon={Eye} label="Total Views" value={formatNumber(summary?.total_views ?? 0)} loading={loading} />
        <MetricCard icon={ThumbsUp} label="Total Likes" value={formatNumber(summary?.total_likes ?? 0)} loading={loading} />
        <MetricCard icon={MessageCircle} label="Comments" value={formatNumber(summary?.total_comments ?? 0)} loading={loading} />
        <MetricCard icon={Bookmark} label="Saves" value={formatNumber(summary?.total_saves ?? 0)} loading={loading} />
        <MetricCard icon={Share2} label="Shares" value={formatNumber(summary?.total_shares ?? 0)} loading={loading} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="animate-fade-in stagger-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" aria-hidden="true" />
              Engagement Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3 py-4">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            ) : hasData ? (
              <div className="grid grid-cols-2 gap-4 py-2 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Avg engagement rate
                  </p>
                  <p className="mt-1 text-2xl font-bold">{summary!.avg_engagement_rate.toFixed(2)}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Avg virality score
                  </p>
                  <p className="mt-1 text-2xl font-bold">{summary!.avg_virality_score.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Reels analyzed
                  </p>
                  <p className="mt-1 text-2xl font-bold">{summary!.total_reels}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-12">
                <p className="text-sm text-zinc-400">Connect an account to see engagement data</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="animate-fade-in stagger-3">
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
                Reels
              </span>
              <div className="flex items-center gap-1 rounded-lg border border-zinc-200 p-0.5 dark:border-zinc-800">
                {REEL_COUNT_OPTIONS.map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => setLimit(count)}
                    className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                      limit === count
                        ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                        : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
                    }`}
                  >
                    {count}
                  </button>
                ))}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3 py-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : summary && (summary.reels ?? []).length > 0 ? (
              <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {(summary.reels ?? []).map((reel) => (
                  <Link
                    key={reel.id}
                    href={`/reel/${reel.instagram_reel_id}`}
                    className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2.5 text-sm transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{reel.instagram_reel_id}</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        {formatNumber(reel.views)} views · {formatNumber(reel.likes)} likes
                      </p>
                    </div>
                    <Badge variant={reel.engagement_rate > 3 ? "success" : "secondary"}>
                      {reel.engagement_rate.toFixed(1)}%
                    </Badge>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-12">
                <p className="text-sm text-zinc-400">No reel data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  loading,
}: {
  icon: React.ElementType
  label: string
  value: string
  loading: boolean
}) {
  return (
    <Card className="animate-fade-in">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-zinc-100 p-2 dark:bg-zinc-800">
            <Icon className="h-4 w-4 text-zinc-600 dark:text-zinc-300" aria-hidden="true" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {label}
            </p>
            {loading ? (
              <Skeleton className="mt-1 h-5 w-16" />
            ) : (
              <p className="text-lg font-bold">{value}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
