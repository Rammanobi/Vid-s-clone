"use client"

import { useState, useEffect, useMemo } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Film, Search, ArrowUpDown, Sparkles, Lightbulb, Hash, AtSign } from "lucide-react"
import { cn, formatNumber } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { api, type ContentReel } from "@/lib/api"

const UNCATEGORIZED = "Uncategorized"

function displayField(value: string | null | undefined): string {
  return value && value.trim().length > 0 ? value : UNCATEGORIZED
}

function mostCommon(values: string[]): string {
  if (values.length === 0) return UNCATEGORIZED
  const counts = new Map<string, number>()
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1)
  let best = values[0]
  let bestCount = 0
  for (const [v, c] of counts) {
    if (c > bestCount) {
      best = v
      bestCount = c
    }
  }
  return best
}

export default function ContentPage() {
  const { token } = useAuth()
  const [reels, setReels] = useState<ContentReel[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [topicFilter, setTopicFilter] = useState("")
  const [sortBy, setSortBy] = useState<"views" | "engagement">("engagement")

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    api.content
      .reels(token, 100)
      .then((result) => setReels(result.reels))
      .catch(() => setReels([]))
      .finally(() => setLoading(false))
  }, [token])

  const topics = useMemo(
    () => [...new Set(reels.map((r) => displayField(r.topic)))],
    [reels]
  )

  const filtered = useMemo(
    () =>
      reels
        .filter(
          (r) =>
            !search ||
            (r.caption ?? "").toLowerCase().includes(search.toLowerCase())
        )
        .filter((r) => !topicFilter || displayField(r.topic) === topicFilter)
        .sort((a, b) =>
          sortBy === "views"
            ? b.views - a.views
            : b.engagement_rate - a.engagement_rate
        ),
    [reels, search, topicFilter, sortBy]
  )

  const hasData = !loading && reels.length > 0

  const topTopic = useMemo(
    () => mostCommon(reels.map((r) => displayField(r.topic))),
    [reels]
  )
  const topHookType = useMemo(
    () => mostCommon(reels.map((r) => displayField(r.hook_type))),
    [reels]
  )
  const topFormat = useMemo(
    () => mostCommon(reels.map((r) => displayField(r.content_format))),
    [reels]
  )

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Content Intelligence</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Explore topics, hooks, and content formats driving engagement
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
                  Connect an Instagram account to see content intelligence here
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="animate-fade-in stagger-1">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-500/10 p-2">
                <Lightbulb className="h-4 w-4 text-blue-500" />
              </div>
              <div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Top Topic</p>
                {loading ? (
                  <Skeleton className="mt-1 h-4 w-20" />
                ) : (
                  <p className="text-sm font-semibold">{hasData ? topTopic : UNCATEGORIZED}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="animate-fade-in stagger-2">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-amber-500/10 p-2">
                <Hash className="h-4 w-4 text-amber-500" />
              </div>
              <div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Best Hook Type</p>
                {loading ? (
                  <Skeleton className="mt-1 h-4 w-20" />
                ) : (
                  <p className="text-sm font-semibold">{hasData ? topHookType : UNCATEGORIZED}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="animate-fade-in stagger-3">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-emerald-500/10 p-2">
                <Sparkles className="h-4 w-4 text-emerald-500" />
              </div>
              <div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Best Format</p>
                {loading ? (
                  <Skeleton className="mt-1 h-4 w-20" />
                ) : (
                  <p className="text-sm font-semibold">{hasData ? topFormat : UNCATEGORIZED}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="animate-fade-in stagger-3">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Film className="h-5 w-5" aria-hidden="true" />
              Content Library
            </span>
            <div className="flex items-center gap-2">
              <Select
                options={topics.map((t) => ({ value: t, label: t }))}
                value={topicFilter}
                onChange={(e) => setTopicFilter(e.target.value)}
                placeholder="All Topics"
                className="w-36"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSortBy(sortBy === "views" ? "engagement" : "views")}
              >
                <ArrowUpDown className="mr-1 h-3 w-3" />
                {sortBy === "views" ? "Views" : "Engagement"}
              </Button>
            </div>
          </CardTitle>
          <div className="relative mt-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" aria-hidden="true" />
            <input
              type="search"
              placeholder="Search reels..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-10 pr-3 text-sm focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400/20 dark:border-zinc-800 dark:bg-zinc-950"
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3 py-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !hasData ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-zinc-400">No reel data available yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800">
                    <th className="px-3 py-2.5 text-left font-medium text-zinc-500 dark:text-zinc-400">Caption</th>
                    <th className="px-3 py-2.5 text-left font-medium text-zinc-500 dark:text-zinc-400">Topic</th>
                    <th className="px-3 py-2.5 text-left font-medium text-zinc-500 dark:text-zinc-400">Hook</th>
                    <th className="px-3 py-2.5 text-left font-medium text-zinc-500 dark:text-zinc-400">Format</th>
                    <th className="px-3 py-2.5 text-right font-medium text-zinc-500 dark:text-zinc-400">Views</th>
                    <th className="px-3 py-2.5 text-right font-medium text-zinc-500 dark:text-zinc-400">Eng.</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((reel, i) => (
                    <tr
                      key={reel.id}
                      className={cn(
                        "border-b border-zinc-100 transition-colors hover:bg-zinc-50 dark:border-zinc-800/50 dark:hover:bg-zinc-900/50",
                        `animate-fade-in stagger-${Math.min(i + 1, 5)}`
                      )}
                    >
                      <td className="max-w-xs truncate px-3 py-3 font-medium">
                        {reel.caption || "—"}
                      </td>
                      <td className="px-3 py-3">
                        <Badge variant="secondary" className="text-[10px]">
                          {displayField(reel.topic)}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-zinc-600 dark:text-zinc-400">
                        {displayField(reel.hook_type)}
                      </td>
                      <td className="px-3 py-3 text-zinc-600 dark:text-zinc-400">
                        {displayField(reel.content_format)}
                      </td>
                      <td className="px-3 py-3 text-right font-medium">
                        {formatNumber(reel.views)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-medium text-emerald-500">
                          {reel.engagement_rate.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
