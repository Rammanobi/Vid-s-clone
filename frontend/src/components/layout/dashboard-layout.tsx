"use client"

import { usePathname } from "next/navigation"
import { Navbar } from "@/components/layout/navbar"
import { Sidebar } from "@/components/layout/sidebar"
import { OnboardingFlow } from "@/components/onboarding/onboarding-flow"

// Reel Bot has its own full-page design (its own header + sidebar, built to
// the exact Stitch mockup) - wrapping it in the app's global navbar/sidebar
// put two navigation shells on screen at once, which isn't what was asked
// for. Every other route keeps the shared shell.
const STANDALONE_ROUTES = ["/reel-bot"]

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isStandalone = STANDALONE_ROUTES.some((route) => pathname?.startsWith(route))

  if (isStandalone) {
    return <>{children}</>
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-auto" id="main-content" role="main">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
      <OnboardingFlow />
    </div>
  )
}
