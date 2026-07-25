"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/lib/auth-context"
import { Save, RefreshCw, Globe, Key, Clock, Bell } from "lucide-react"

export default function SettingsPage() {
  const { token, user, logout } = useAuth()
  const [saving, setSaving] = useState(false)

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
            <CardTitle className="flex items-center gap-2 text-base">
              <Clock className="h-4 w-4" aria-hidden="true" />
              Pipeline Schedule
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input label="Update Interval (hours)" defaultValue="24" type="number" min={1} max={168} />
            <Button size="sm" loading={saving}>
              <Save className="mr-1 h-3.5 w-3.5" />
              Save Settings
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
