import Link from "next/link"
import { Frown } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center animate-fade-in">
      <Frown className="mb-4 h-16 w-16 text-zinc-300 dark:text-zinc-600" aria-hidden="true" />
      <h1 className="text-4xl font-bold tracking-tight">404</h1>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/dashboard">
        <Button className="mt-6">Go to Dashboard</Button>
      </Link>
    </div>
  )
}
