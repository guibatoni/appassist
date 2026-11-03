import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type PanelProps = {
  title?: React.ReactNode
  icon?: LucideIcon
  action?: React.ReactNode
  className?: string
  bodyClassName?: string
  children: React.ReactNode
  as?: "section" | "div" | "aside"
}

export function Panel({ title, icon: Icon, action, className, bodyClassName, children, as: Tag = "section" }: PanelProps) {
  return (
    <Tag className={cn("panel flex flex-col", className)}>
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-line/50 px-4 py-2.5">
          <h2 className="flex items-center gap-2 font-display text-[15px] font-semibold text-white">
            {Icon && <Icon className="size-5 text-primary" aria-hidden="true" />}
            {title}
          </h2>
          {action}
        </div>
      )}
      <div className={cn("flex-1 p-3", bodyClassName)}>{children}</div>
    </Tag>
  )
}

export function Pill({ children, tone = "gold", className }: { children: React.ReactNode; tone?: "gold" | "violet" | "green" | "muted"; className?: string }) {
  const tones = {
    gold: "border-gold/70 bg-gold/15 text-gold",
    violet: "border-violet/70 bg-violet/15 text-[#d3a8ff]",
    green: "border-success/60 bg-success/15 text-success",
    muted: "border-line bg-panel-strong text-muted",
  }
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium", tones[tone], className)}>
      {children}
    </span>
  )
}

export function ProgressBar({ value, tone = "cyan", segmented, className }: { value: number; tone?: "cyan" | "green" | "purple"; segmented?: boolean; className?: string }) {
  const fills = {
    cyan: "from-[#1f8fff] to-primary",
    green: "from-[#1fae5a] to-success",
    purple: "from-[#7a2fe0] to-violet",
  }
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-2 overflow-hidden rounded-full bg-[#0a1a3a] ring-1 ring-line/60", className)}
    >
      <div
        className={cn("h-full rounded-full bg-gradient-to-r shadow-[0_0_10px_currentColor] transition-[width] duration-700", fills[tone])}
        style={{
          width: `${value}%`,
          ...(segmented && { maskImage: "repeating-linear-gradient(90deg,#000 0 calc(10% - 3px),transparent calc(10% - 3px) 10%)" }),
        }}
      />
    </div>
  )
}
