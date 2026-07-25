"use client"

import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type PipelineHealth, type PipelineRunResponse } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { formatRelativeTime, getStatusBg, getStatusColor } from "@/lib/utils"
import { GitBranch, Play, RefreshCw, Clock, AlertTriangle, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

const stageDescriptions: Record<string, string> = {
  ingestion: "Fetch reels & comments from HikerAPI",
  enrichment: "Transcription, OCR, CLIP embedding",
  analytics: "Engagement metrics & snapshots",
  intelligence: "Content topic, hooks, format extraction",
  knowledge: "Creator profile building",
  agent: "LangGraph agent compilation check",
  retrieval: "Hybrid retrieval pipeline verification",
}

export default function PipelinePage() {
  const { token } = useAuth()
  const [health, setHealth] = useState<PipelineHealth | null>(null)
  const [stagesInfo, setStagesInfo] = useState<{ stages: string[]; description: Record<string, string> } | null>(null)
  const [lastRun, setLastRun] = useState<PipelineRunResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [h, s] = await Promise.all([
        api.health.pipeline(token || undefined).catch(() => null),
        api.pipeline.stages().catch(() => null),
      ])
      setHealth(h)
      setStagesInfo(s)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  const runPipeline = async () => {
    setRunning(true)
    try {
      const result = await api.pipeline.run(token || undefined)
      setLastRun(result)
    } finally {
      setRunning(false)
    }
  }

  const stages = stagesInfo?.stages || health?.stages || []

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Pipeline</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage the data processing pipeline and monitor stage health
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {loading ? (
            <Skeleton className="h-6 w-32" />
          ) : (
            <>
              <div
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  health?.status === "healthy"
                    ? "bg-emerald-500"
                    : health?.status === "degraded"
                      ? "bg-amber-500"
                      : "bg-zinc-300 dark:bg-zinc-600"
                )}
              />
              <span className="text-sm font-medium capitalize">
                {health?.status || "Unknown"}
              </span>
              {health && (
                <span className="text-xs text-zinc-400">
                  {health.pipeline.consecutive_failures > 0 &&
                    `${health.pipeline.consecutive_failures} consecutive failures`}
                </span>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
            Refresh
          </Button>
          <Button size="sm" loading={running} onClick={runPipeline}>
            <Play className="mr-1 h-3.5 w-3.5" />
            Run Pipeline
          </Button>
        </div>
      </div>

      {lastRun && (
        <Card className="animate-fade-in border-amber-200 dark:border-amber-800">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-amber-500" aria-hidden="true" />
              <span>Last run: </span>
              <span className="font-medium capitalize">{lastRun.status}</span>
              <span className="text-zinc-400">in {lastRun.elapsed_sec.toFixed(2)}s</span>
              <span className="text-zinc-400">·</span>
              <span className="text-xs text-zinc-400">ID: {lastRun.pipeline_run_id.slice(0, 8)}...</span>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {loading
          ? Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))
          : stages.map((stage, i) => {
              const desc = stagesInfo?.description?.[stage] || stageDescriptions[stage] || ""
              const runStage = lastRun?.stages.find((s) => s.name === stage)
              return (
                <StageCard
                  key={stage}
                  stage={stage}
                  description={desc}
                  index={i}
                  runStage={runStage}
                />
              )
            })}
      </div>
    </div>
  )
}

function StageCard({
  stage,
  description,
  index,
  runStage,
}: {
  stage: string
  description: string
  index: number
  runStage?: { name: string; status: string; elapsed_sec: number; error?: string }
}) {
  const statusIcon = runStage
    ? runStage.status === "success"
      ? CheckCircle2
      : runStage.status === "failed"
        ? XCircle
        : AlertTriangle
    : GitBranch

  return (
    <Card className={cn("animate-fade-in", `stagger-${Math.min(index + 1, 5)}`)}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                "mt-0.5 rounded-lg p-2",
                runStage?.status === "success"
                  ? "bg-emerald-500/10"
                  : runStage?.status === "failed"
                    ? "bg-red-500/10"
                    : "bg-zinc-100 dark:bg-zinc-800"
              )}
            >
              <statusIcon
                className={cn(
                  "h-4 w-4",
                  runStage?.status === "success"
                    ? "text-emerald-500"
                    : runStage?.status === "failed"
                      ? "text-red-500"
                      : "text-zinc-500 dark:text-zinc-400"
                )}
                aria-hidden="true"
              />
            </div>
            <div>
              <h3 className="text-sm font-semibold capitalize">{stage}</h3>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {runStage && (
              <>
                <Badge
                  variant={
                    runStage.status === "success"
                      ? "success"
                      : runStage.status === "failed"
                        ? "destructive"
                        : "warning"
                  }
                  className="text-[10px]"
                >
                  {runStage.status}
                </Badge>
                <span className="text-[10px] text-zinc-400">
                  {runStage.elapsed_sec.toFixed(1)}s
                </span>
              </>
            )}
          </div>
        </div>
        {runStage?.error && (
          <p className="mt-2 text-xs text-red-500">{runStage.error}</p>
        )}
      </CardContent>
    </Card>
  )
}
