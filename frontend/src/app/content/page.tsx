"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Film, Search, ArrowUpDown, Sparkles, Lightbulb, Hash, Music } from "lucide-react"
import { cn } from "@/lib/utils"

const placeholderReels = [
  { id: "1", caption: "How I grew my account 10x in 30 days 🔥", views: "2.3M", engagement: "8.5%", topic: "Growth Tips", hookType: "Curiosity", format: "Talking Head", sentiment: "Positive" },
  { id: "2", caption: "The ONE mistake stopping your growth 🛑", views: "1.1M", engagement: "12.3%", topic: "Growth Tips", hookType: "Contrarian", format: "Talking Head", sentiment: "Neutral" },
  { id: "3", caption: "Behind the scenes of a $10K brand deal 📸", views: "890K", engagement: "6.2%", topic: "Monetization", hookType: "Story", format: "Behind the Scenes", sentiment: "Positive" },
  { id: "4", caption: "Stop posting at these times ⏰", views: "2.1M", engagement: "15.1%", topic: "Strategy", hookType: "Problem Solution", format: "Tutorial", sentiment: "Neutral" },
  { id: "5", caption: "Reacting to my first video vs now 😂", views: "4.5M", engagement: "9.8%", topic: "Personal", hookType: "Story", format: "Talking Head", sentiment: "Positive" },
]

const topics = [...new Set(placeholderReels.map((r) => r.topic))]
const hookTypes = [...new Set(placeholderReels.map((r) => r.hookType))]
const formats = [...new Set(placeholderReels.map((r) => r.format))]

export default function ContentPage() {
  const [search, setSearch] = useState("")
  const [topicFilter, setTopicFilter] = useState("")
  const [sortBy, setSortBy] = useState<"views" | "engagement">("engagement")

  const filtered = placeholderReels
    .filter((r) => !search || r.caption.toLowerCase().includes(search.toLowerCase()))
    .filter((r) => !topicFilter || r.topic === topicFilter)
    .sort((a, b) =>
      sortBy === "views"
        ? Number(b.views.replace(/[^0-9.]/g, "")) - Number(a.views.replace(/[^0-9.]/g, ""))
        : Number(b.engagement.replace("%", "")) - Number(a.engagement.replace("%", ""))
    )

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">Content Intelligence</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Explore topics, hooks, and content formats driving engagement
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="animate-fade-in stagger-1">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-500/10 p-2">
                <Lightbulb className="h-4 w-4 text-blue-500" />
              </div>
              <div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Top Topic</p>
                <p className="text-sm font-semibold">Growth Tips</p>
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
                <p className="text-sm font-semibold">Story</p>
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
                <p className="text-sm font-semibold">Tutorial</p>
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
                    <td className="max-w-xs truncate px-3 py-3 font-medium">{reel.caption}</td>
                    <td className="px-3 py-3">
                      <Badge variant="secondary" className="text-[10px]">{reel.topic}</Badge>
                    </td>
                    <td className="px-3 py-3 text-zinc-600 dark:text-zinc-400">{reel.hookType}</td>
                    <td className="px-3 py-3 text-zinc-600 dark:text-zinc-400">{reel.format}</td>
                    <td className="px-3 py-3 text-right font-medium">{reel.views}</td>
                    <td className="px-3 py-3 text-right">
                      <span className="font-medium text-emerald-500">{reel.engagement}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
