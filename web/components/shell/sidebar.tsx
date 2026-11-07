"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Cpu, House, Infinity as InfinityIcon, Layers, MonitorPlay, Settings, Swords, Gift } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Início", href: "/inicio", icon: House, enabled: true },
  { label: "Biblioteca de Mods", href: "/mods", icon: Cpu, enabled: true },
  { label: "Biblioteca de Cartas", href: "/biblioteca", icon: Layers, enabled: true },
  { label: "Fusões", href: "/fusoes", icon: InfinityIcon, enabled: true },
  { label: "Drops", href: "/drops", icon: Gift, enabled: true },
]

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

    </aside>
  )
}
