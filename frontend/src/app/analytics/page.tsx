"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth-context"
import { formatNumber, formatRelativeTime, getStatusColor } from "@/lib/utils"
import { BarChart3, Eye, ThumbsUp, MessageCircle, Bookmark, Share2, TrendingUp } from "lucide-react"

export default function AnalyticsPage() {
  const { token } = useAuth()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(false)
  }, [token])

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Performance metrics and engagement analysis
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard icon={Eye} label="Total Views" value="--" loading={loading} />
        <MetricCard icon={ThumbsUp} label="Total Likes" value="--" loading={loading} />
        <MetricCard icon={MessageCircle} label="Comments" value="--" loading={loading} />
        <MetricCard icon={Bookmark} label="Saves" value="--" loading={loading} />
        <MetricCard icon={Share2} label="Shares" value="--" loading={loading} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="animate-fade-in stagger-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" aria-hidden="true" />
              Engagement Rate Over Time
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center py-12">
            <p className="text-sm text-zinc-400">
              Connect to the API to see engagement charts
            </p>
          </CardContent>
        </Card>

        <Card className="animate-fade-in stagger-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4" aria-hidden="true" />
              Top Performing Reels
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center py-12">
            <p className="text-sm text-zinc-400">
              No reel data available yet
            </p>
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
