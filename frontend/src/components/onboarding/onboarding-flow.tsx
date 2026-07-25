"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ArrowRight, ArrowLeft, Check, Sparkles, Film, BarChart3, Bot, GitBranch } from "lucide-react"

const steps = [
  {
    title: "Welcome to Vid's Clone",
    description: "Your AI-powered content strategy platform for Instagram Reels. Let's get you set up in a few steps.",
    icon: Sparkles,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
  },
  {
    title: "Connect Your Data",
    description: "Start by ingesting your Instagram accounts and reels. The pipeline will automatically fetch and enrich your content.",
    icon: Film,
    color: "text-amber-500",
    bg: "bg-amber-500/10",
  },
  {
    title: "Analyze Performance",
    description: "View engagement metrics, virality scores, and performance trends for all your reels.",
    icon: BarChart3,
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
  },
  {
    title: "Get AI Insights",
    description: "Use the AI Agent to ask questions about your content strategy and get data-driven recommendations.",
    icon: Bot,
    color: "text-purple-500",
    bg: "bg-purple-500/10",
  },
  {
    title: "Run the Pipeline",
    description: "The pipeline processes data through 7 stages: ingestion, enrichment, analytics, intelligence, knowledge, agent, and retrieval.",
    icon: GitBranch,
    color: "text-rose-500",
    bg: "bg-rose-500/10",
  },
]

export function OnboardingFlow() {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)
  const completed = typeof window !== "undefined" && localStorage.getItem("onboarding_completed")

  useEffect(() => {
    if (!completed) {
      const timer = setTimeout(() => setOpen(true), 500)
      return () => clearTimeout(timer)
    }
  }, [completed])

  const finish = () => {
    localStorage.setItem("onboarding_completed", "true")
    setOpen(false)
  }

  const current = steps[step]
  if (!current) return null

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Onboarding"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="w-full max-w-lg"
          >
            <Card>
              <CardContent className="p-8">
                <div className="flex flex-col items-center text-center">
                  <div className={`mb-4 rounded-2xl p-4 ${current.bg}`}>
                    <current.icon className={`h-8 w-8 ${current.color}`} aria-hidden="true" />
                  </div>
                  <h2 className="text-xl font-semibold">{current.title}</h2>
                  <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
                    {current.description}
                  </p>

                  <div className="mt-8 flex gap-1.5">
                    {steps.map((_, i) => (
                      <div
                        key={i}
                        className={`h-1.5 w-6 rounded-full transition-colors ${
                          i === step
                            ? "bg-zinc-900 dark:bg-zinc-50"
                            : i < step
                              ? "bg-emerald-500"
                              : "bg-zinc-200 dark:bg-zinc-800"
                        }`}
                      />
                    ))}
                  </div>

                  <div className="mt-8 flex w-full gap-3">
                    {step > 0 && (
                      <Button
                        variant="outline"
                        onClick={() => setStep(step - 1)}
                        className="flex-1"
                      >
                        <ArrowLeft className="mr-1 h-4 w-4" />
                        Back
                      </Button>
                    )}
                    {step < steps.length - 1 ? (
                      <Button onClick={() => setStep(step + 1)} className="flex-1">
                        Next
                        <ArrowRight className="ml-1 h-4 w-4" />
                      </Button>
                    ) : (
                      <Button onClick={finish} className="flex-1">
                        <Check className="mr-1 h-4 w-4" />
                        Get Started
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
