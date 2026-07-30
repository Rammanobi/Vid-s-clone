"use client"

interface StatBadgeProps {
  label: string
  value: string | number
  icon?: string
  variant?: "default" | "success" | "warning" | "info"
}

export function StatBadge({ label, value, icon, variant = "default" }: StatBadgeProps) {
  const variants = {
    default: "bg-amber-600/20 border-amber-600/30 text-amber-300",
    success: "bg-green-600/20 border-green-600/30 text-green-300",
    warning: "bg-orange-600/20 border-orange-600/30 text-orange-300",
    info: "bg-blue-600/20 border-blue-600/30 text-blue-300",
  }

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border ${variants[variant]}`}>
      {icon && <span className="text-lg">{icon}</span>}
      <div>
        <div className="text-xs font-medium opacity-70">{label}</div>
        <div className="text-sm font-bold">{value}</div>
      </div>
    </div>
  )
}
