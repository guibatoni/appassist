"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Cpu, House, Infinity as InfinityIcon, Layers, MonitorPlay, Settings, Swords } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Início", href: "/inicio", icon: House, enabled: true },
  { label: "Biblioteca de Mods", href: "/mods", icon: Cpu, enabled: true },
  { label: "Biblioteca de Cartas", href: "/biblioteca", icon: Layers, enabled: true },
  { label: "Fusões", href: "/fusoes", icon: InfinityIcon, enabled: true },
]

function EyeOfHorus() {
  return (
    <svg viewBox="0 0 120 80" className="w-28 drop-shadow-[0_0_12px_rgb(245_184_61/0.6)]" aria-hidden="true">
      <g fill="none" stroke="#f5b83d" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 22c20-14 60-16 96-4" />
        <path d="M16 38c16-14 52-14 72 0-20 12-52 12-72 0z" />
        <circle cx="52" cy="38" r="8" fill="#f5b83d" />
        <path d="M88 38h22" />
        <path d="M46 48l-6 22c-2 6-10 6-12 0" />
        <path d="M60 48l20 20" />
      </g>
    </svg>
  )
}

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="lg:w-56 lg:shrink-0">
      <nav aria-label="Navegação principal">
        <ul className="flex gap-1 overflow-x-auto pb-1 scrollbar-thin lg:flex-col lg:gap-1.5 lg:overflow-visible lg:pb-0">
          {navItems.map(({ label, href, icon: Icon, enabled }) => {
            const active = pathname.startsWith(href)
            const className = cn(
              "group flex shrink-0 items-center gap-3 whitespace-nowrap rounded-lg border px-3 py-2.5 text-sm transition-all lg:px-4 lg:py-3 lg:text-[15px]",
              active
                ? "border-primary bg-gradient-to-r from-primary/30 to-primary/5 font-semibold text-white shadow-[0_0_18px_rgb(56_200_255/0.45),inset_0_0_12px_rgb(56_200_255/0.25)]"
                : "border-transparent text-foreground/85 hover:border-line hover:bg-primary/5 hover:text-white",
            )
            const icon = (
              <Icon className={cn("size-5 shrink-0 transition-colors", active ? "text-white" : "text-foreground/70 group-hover:text-primary")} />
            )
            return (
              <li key={href}>
                {enabled ? (
                  <Link href={href} className={className} aria-current={active ? "page" : undefined}>
                    {icon}
                    {label}
                  </Link>
                ) : (
                  <span className={cn(className, "cursor-default")} title="Em breve" aria-disabled="true">
                    {icon}
                    {label}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="relative mt-8 hidden flex-col items-center gap-4 lg:flex" aria-hidden="true">
        <div className="h-24 w-px bg-gradient-to-b from-transparent via-gold to-gold/40" />
        <EyeOfHorus />
        <div className="flex items-end gap-1.5">
          {[40, 64, 88, 56, 36].map((h, i) => (
            <span
              key={i}
              className="w-4 bg-gradient-to-t from-primary/80 to-white/90 shadow-[0_0_16px_rgb(56_200_255/0.8)]"
              style={{ height: h, clipPath: "polygon(50% 0, 100% 18%, 100% 100%, 0 100%, 0 18%)" }}
            />
          ))}
        </div>
      </div>
    </aside>
  )
}
