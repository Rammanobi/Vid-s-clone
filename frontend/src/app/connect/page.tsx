"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { api, type Account } from "@/lib/api"
import { ProfileCard } from "@/components/profile-card"
import { setPersistent } from "@/lib/cache"
import { AtSign, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"

const CONNECTED_USERNAME_KEY = "connected_username"

// The backend response shape may include extra/varying fields depending on
// the ingestion pipeline's stage - handle it defensively rather than
// hard-failing on a missing field.
interface IngestAccountResult {
  status?: string
  account_id?: string
  username?: string
  reels_ingested?: number
  pipeline_status?: string
  account?: { id?: string; username?: string }
}

export default function ConnectPage() {
  const { token } = useAuth()
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [maxReels, setMaxReels] = useState("3")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IngestAccountResult | null>(null)
  const [profile, setProfile] = useState<Account | null>(null)

  const reelsFound = result?.reels_ingested

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return

    const cleaned = username.trim().replace(/^@/, "")
    if (!cleaned) {
      setError("Enter an Instagram username")
      return
    }
    if (!token) {
      setError("Sign in before connecting an account")
      return
    }

    setError(null)
    setResult(null)
    setLoading(true)

    try {
      const res = (await api.ingest.account(
        token,
        cleaned,
        Number(maxReels)
      )) as unknown as IngestAccountResult
      if (res && (res.status === "ok" || res.status === "success" || res.account || res.account_id)) {
        setResult(res)
        setPersistent(CONNECTED_USERNAME_KEY, cleaned)

        // Fetch the full profile (bio, avatar, verified badge, etc.) so the
        // user sees what was actually ingested - the /ingest/account POST
        // response only echoes back {status, account_id, reels_ingested, ...}.
        api.ingest
          .getAccount(token, cleaned)
          .then((acct) => setProfile(acct))
          .catch(() => {
            // Non-fatal - the connect flow itself already succeeded.
          })

        setTimeout(() => router.push("/agent"), 2500)
      } else {
        setError(
          `Could not connect @${cleaned}. ${res?.status ? `Status: ${res.status}` : "Unexpected response from server."}`
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect account")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Connect Instagram</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Link an Instagram account to chat with its content
        </p>
      </div>

      <Card className="animate-fade-in stagger-1">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AtSign className="h-4 w-4" aria-hidden="true" />
            Instagram Username
          </CardTitle>
          <CardDescription>
            We&apos;ll fetch recent Reels, captions, and comments so the AI agent can answer
            questions about this account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Username"
              placeholder="okaashish"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading || !!result}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
            />
            <Select
              label="Reels to fetch"
              value={maxReels}
              onChange={(e) => setMaxReels(e.target.value)}
              disabled={loading || !!result}
              options={Array.from({ length: 10 }, (_, i) => {
                const n = i + 1
                return { value: String(n), label: `${n} reel${n > 1 ? "s" : ""}` }
              })}
            />
            <p className="text-xs text-zinc-400">
              Each reel costs one API call to fetch its comments - start small.
            </p>
            <Button
              type="submit"
              className="w-full"
              loading={loading}
              disabled={loading || !username.trim() || !!result}
            >
              {!loading && "Connect Account"}
            </Button>
          </form>

          {loading && (
            <div className="flex items-start gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
              <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />
              <span>
                Fetching your Reels from Instagram - this can take a minute. We&apos;re pulling
                video metadata and comments, please don&apos;t close this page.
              </span>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-400">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>
                Connected!{" "}
                {typeof reelsFound === "number" ? `Found ${reelsFound} reels. ` : ""}
                Taking you to chat...
              </span>
            </div>
          )}

          {result && (
            <Button variant="outline" size="sm" className="w-full" onClick={() => router.push("/agent")}>
              Go to chat now
            </Button>
          )}
        </CardContent>
      </Card>

      {profile && <ProfileCard account={profile} className="animate-fade-in" />}
    </div>
  )
}
