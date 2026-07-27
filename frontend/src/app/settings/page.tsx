"use client"

import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/lib/auth-context"
import { api, type ApiHealth, type PipelineHealth } from "@/lib/api"
import { RefreshCw, Globe, Key, Activity } from "lucide-react"

export default function SettingsPage() {
  const { token, user, logout } = useAuth()
  const [health, setHealth] = useState<ApiHealth | null>(null)
  const [pipelineHealth, setPipelineHealth] = useState<PipelineHealth | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [h, p] = await Promise.all([
        api.health.check(token || undefined).catch(() => null),
        api.health.pipeline(token || undefined).catch(() => null),
      ])
      setHealth(h)
      setPipelineHealth(p)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage your account and application preferences
        </p>
      </div>

      <div className="grid gap-6">
        <Card className="animate-fade-in stagger-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Key className="h-4 w-4" aria-hidden="true" />
              Account
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-zinc-100 px-4 py-3 dark:border-zinc-800">
              <div>
                <p className="text-sm font-medium">Signed in as</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{user || "Not signed in"}</p>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <Button variant="destructive" size="sm" onClick={logout}>
              Sign Out
            </Button>
          </CardContent>
        </Card>

        <Card className="animate-fade-in stagger-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Globe className="h-4 w-4" aria-hidden="true" />
              API Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="API URL"
              defaultValue={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
              disabled
            />
            <Input label="Access Token" value={token || "Not configured"} disabled type="password" />
          </CardContent>
        </Card>

        <Card className="animate-fade-in stagger-3">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span className="flex items-center gap-2">
                <Activity className="h-4 w-4" aria-hidden="true" />
                System Status
              </span>
              <Button variant="outline" size="sm" onClick={load}>
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                Refresh
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between rounded-lg border border-zinc-100 px-4 py-3 dark:border-zinc-800">
                  <div>
                    <p className="text-sm font-medium">API</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      Database: {health?.database || "unknown"}
                      {health?.version ? ` · v${health.version}` : ""}
                    </p>
                  </div>
                  <Badge variant={health?.status === "healthy" ? "success" : "warning"}>
                    {health?.status || "unknown"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-zinc-100 px-4 py-3 dark:border-zinc-800">
                  <div>
                    <p className="text-sm font-medium">Pipeline</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {pipelineHealth
                        ? `${pipelineHealth.pipeline.consecutive_failures} consecutive failures`
                        : "Unable to reach pipeline health check"}
                    </p>
                  </div>
                  <Badge
                    variant={pipelineHealth?.status === "healthy" ? "success" : "warning"}
                  >
                    {pipelineHealth?.status || "unknown"}
                  </Badge>
                </div>
              </>
            )}
            <p className="text-xs text-zinc-400">
              Preferences aren&apos;t stored anywhere yet - this section only shows live system status.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
