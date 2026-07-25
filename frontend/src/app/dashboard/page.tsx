"use client"

import { useState, useEffect } from "react"
import { Activity, Film, TrendingUp, AlertCircle, Play, GitBranch, Sparkles } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type ApiHealth, type PipelineHealth } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { formatRelativeTime, formatNumber, getStatusColor } from "@/lib/utils"

export default function DashboardPage() {
  const { token } = useAuth()
  const [health, setHealth] = useState<Record<string, ApiHealth | null>>({})
  const [pipeline, setPipeline] = useState<PipelineHealth | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [h, a, c, cr, k, p] = await Promise.all([
          api.health.check(token || undefined).catch(() => null),
          api.health.analytics().catch(() => null),
          api.health.content().catch(() => null),
          api.health.creator().catch(() => null),
          api.health.knowledge().catch(() => null),
          api.health.pipeline(token || undefined).catch(() => null),
        ])
        setHealth({ main: h, analytics: a, content: c, creator: cr, knowledge: k })
        setPipeline(p)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [token])

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Overview of your content strategy platform
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Reels Tracked"
          value={health.main?.reel_count ?? 0}
          icon={Film}
          loading={loading}
          delay="stagger-1"
        />
        <StatsCard
          title="Pipeline Status"
          value={pipeline?.status ?? "unknown"}
          icon={GitBranch}
          loading={loading}
          delay="stagger-2"
          color={pipeline?.status === "healthy" ? "text-emerald-500" : "text-amber-500"}
        />
        <StatsCard
          title="Content Intelligence"
          value={health.content?.intelligence_count ?? 0}
          icon={Sparkles}
          loading={loading}
          delay="stagger-3"
        />
        <StatsCard
          title="Creator Profile"
          value={health.creator?.profile_exists ? "Active" : "Inactive"}
          icon={TrendingUp}
          loading={loading}
          delay="stagger-4"
          color={health.creator?.profile_exists ? "text-emerald-500" : "text-zinc-400"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <PipelineStatusCard pipeline={pipeline} loading={loading} />
        <ServiceHealthCard health={health} loading={loading} />
      </div>
    </div>
  )
}

function StatsCard({
  title,
  value,
  icon: Icon,
  loading,
  delay = "",
  color,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  loading: boolean
  delay?: string
  color?: string
}) {
  return (
    <Card className={`animate-fade-in ${delay}`}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {title}
            </p>
            {loading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <p className={`text-2xl font-bold ${color || ""}`}>
                {typeof value === "number" ? formatNumber(value) : value}
              </p>
            )}
          </div>
          <div className="rounded-lg bg-zinc-100 p-2.5 dark:bg-zinc-800">
            <Icon className="h-5 w-5 text-zinc-600 dark:text-zinc-300" aria-hidden="true" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function PipelineStatusCard({
  pipeline,
  loading,
}: {
  pipeline: PipelineHealth | null
  loading: boolean
}) {
  const [running, setRunning] = useState(false)

  return (
    <Card className="animate-fade-in stagger-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch className="h-5 w-5" aria-hidden="true" />
          Pipeline Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : pipeline ? (
          <>
            <div className="flex items-center gap-2">
              <div
                className={`h-2.5 w-2.5 rounded-full ${
                  pipeline.status === "healthy"
                    ? "bg-emerald-500"
                    : pipeline.status === "degraded"
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
              />
              <span className="text-sm font-medium capitalize">{pipeline.status}</span>
              <Badge
                variant={
                  pipeline.pipeline.scheduler_running ? "success" : "destructive"
                }
                className="ml-auto"
              >
                {pipeline.pipeline.scheduler_running ? "Running" : "Stopped"}
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">Consecutive Failures</span>
                <p
                  className={`font-medium ${
                    pipeline.pipeline.consecutive_failures >= 3
                      ? "text-red-500"
                      : pipeline.pipeline.consecutive_failures > 0
                        ? "text-amber-500"
                        : ""
                  }`}
                >
                  {pipeline.pipeline.consecutive_failures}
                </p>
              </div>
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">Alert Threshold</span>
                <p className="font-medium">{pipeline.pipeline.alert_threshold}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {pipeline.stages.map((stage) => (
                <Badge key={stage} variant="outline" className="text-[10px] uppercase">
                  {stage}
                </Badge>
              ))}
            </div>
            <Button
              size="sm"
              loading={running}
              onClick={async () => {
                setRunning(true)
                try {
                  const { api } = await import("@/lib/api")
                  await api.pipeline.run(token || undefined)
                } finally {
                  setRunning(false)
                }
              }}
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
              Run Pipeline
            </Button>
          </>
        ) : (
          <p className="text-sm text-zinc-500">Unable to load pipeline status</p>
        )}
      </CardContent>
    </Card>
  )
}

function ServiceHealthCard({
  health,
  loading,
}: {
  health: Record<string, ApiHealth | null>
  loading: boolean
}) {
  const services = [
    { key: "main", label: "API Server" },
    { key: "analytics", label: "Analytics" },
    { key: "content", label: "Content Intelligence" },
    { key: "creator", label: "Creator Intelligence" },
    { key: "knowledge", label: "Knowledge" },
  ]

  return (
    <Card className="animate-fade-in stagger-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" aria-hidden="true" />
          Service Health
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {services.map((svc) => {
              const h = health[svc.key]
              const isHealthy = h?.status === "healthy" || h?.status === "ok"
              return (
                <div
                  key={svc.key}
                  className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2.5 dark:border-zinc-800"
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`h-2 w-2 rounded-full ${
                        h ? (isHealthy ? "bg-emerald-500" : "bg-red-500") : "bg-zinc-300 dark:bg-zinc-600"
                      }`}
                    />
                    <span className="text-sm font-medium">{svc.label}</span>
                  </div>
                  <div className="text-right">
                    {h ? (
                      <span
                        className={`text-xs font-medium ${
                          isHealthy ? "text-emerald-500" : "text-red-500"
                        }`}
                      >
                        {h.status}
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-400">Unreachable</span>
                    )}
                    {h?.last_run && (
                      <p className="text-[10px] text-zinc-400">
                        {formatRelativeTime(h.last_run)}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
