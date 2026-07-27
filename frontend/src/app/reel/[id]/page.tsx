"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/lib/auth-context"
import { api, type ReelDetail } from "@/lib/api"
import { formatNumber } from "@/lib/utils"
import {
  ArrowLeft,
  Eye,
  ThumbsUp,
  MessageCircle,
  Bookmark,
  Share2,
  TrendingUp,
  Sparkles,
  ExternalLink,
} from "lucide-react"

export default function ReelDetailPage() {
  const params = useParams<{ id: string }>()
  const { token } = useAuth()
  const [reel, setReel] = useState<ReelDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!token || !params?.id) {
      setLoading(false)
      return
    }

    setLoading(true)
    setNotFound(false)
    api.ingest
      .reel(token, params.id)
      .then((result) => setReel(result))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [token, params?.id])

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <Link
          href="/analytics"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-500 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to Analytics
        </Link>
        <h1 className="mt-3 text-3xl font-bold tracking-tight">Reel Detail</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          {loading ? "Loading..." : reel ? reel.instagramReelId : params?.id}
        </p>
      </div>

      {loading ? (
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      ) : notFound || !reel ? (
        <Card className="animate-fade-in">
          <CardContent className="flex flex-col items-center justify-center gap-2 py-16">
            <p className="text-sm font-medium">Reel not found</p>
            <p className="text-sm text-zinc-400">
              This reel could not be loaded. It may not have been ingested yet.
            </p>
            <Link
              href="/analytics"
              className="mt-2 text-sm font-medium text-zinc-900 underline underline-offset-4 dark:text-zinc-50"
            >
              Back to Analytics
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2 text-base">
                <span>Caption</span>
                {reel.videoUrl && (
                  <a
                    href={reel.videoUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-normal text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
                  >
                    View source video
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
                {reel.caption || "No caption"}
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Posted{" "}
                {reel.postedAt
                  ? new Date(reel.postedAt).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "unknown date"}
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard icon={Eye} label="Views" value={formatNumber(reel.views ?? 0)} />
            <MetricCard icon={ThumbsUp} label="Likes" value={formatNumber(reel.likes ?? 0)} />
            <MetricCard
              icon={MessageCircle}
              label="Comments"
              value={formatNumber(reel.commentsCount ?? 0)}
            />
            <MetricCard icon={Bookmark} label="Saves" value={formatNumber(reel.saves ?? 0)} />
            <MetricCard icon={Share2} label="Shares" value={formatNumber(reel.shares ?? 0)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="animate-fade-in stagger-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <TrendingUp className="h-4 w-4" aria-hidden="true" />
                  Engagement
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 py-2 text-sm">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      Engagement rate
                    </p>
                    <p className="mt-1 text-2xl font-bold">
                      {(reel.engagementRate ?? 0).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      Virality score
                    </p>
                    <p className="mt-1 text-2xl font-bold">
                      {(reel.viralityScore ?? 0).toFixed(2)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="animate-fade-in stagger-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-2 py-2 text-sm">
                  <Badge variant={( reel.engagementRate ?? 0) > 3 ? "success" : "secondary"}>
                    {(reel.engagementRate ?? 0).toFixed(1)}% engagement
                  </Badge>
                  <Badge variant="secondary">{formatNumber(reel.views ?? 0)} views</Badge>
                  {(reel.views ?? 0) === 0 && (
                    <span className="text-xs text-zinc-400">
                      No views recorded yet for this reel
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType
  label: string
  value: string
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
            <p className="text-lg font-bold">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
