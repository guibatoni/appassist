"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Cpu, House, Infinity as InfinityIcon, Layers, Gift, Users, BookMarked, Settings2 } from "lucide-react"
import { cn } from "@/lib/utils"
import {T,useI18n} from "@/lib/i18n"

const navItems = [
  { label: "Início", href: "/inicio", icon: House, enabled: true },
  { label: "Biblioteca de Mods", href: "/mods", icon: Cpu, enabled: true },
  { label: "Biblioteca de Cartas", href: "/biblioteca", icon: Layers, enabled: true },
  { label: "Fusões", href: "/fusoes", icon: InfinityIcon, enabled: true },
  { label: "Drops", href: "/drops", icon: Gift, enabled: true },
  { label: "Oponentes", href: "/oponentes", icon: Users, enabled: true },
  { label: "Decks", href: "/decks", icon: BookMarked, enabled: true },
  { label: "Meus Decks", href: "/decks-salvos", icon: BookMarked, enabled: true },
  { label: "Configurações", href: "/configuracoes", icon: Settings2, enabled: true },
]

export function Sidebar() {
  const pathname = usePathname()
  const {t}=useI18n()

  return (
    <aside className="dt-nav-sidebar min-w-0 lg:w-56 lg:shrink-0">
      <nav aria-label={t("Navegação principal")}>
        <ul className="dt-nav-list grid grid-cols-3 gap-1 min-[600px]:grid-cols-4 lg:grid-cols-1 lg:flex lg:flex-col lg:gap-1.5">
          {navItems.map(({ label, href, icon: Icon, enabled }) => {
            const active = pathname === href || pathname.startsWith(href + "/")
            const className = cn(
              "dt-nav-link group flex min-w-0 flex-col items-center justify-center gap-1 rounded-lg border px-1 py-2 text-center text-[11px] leading-tight transition-all min-[600px]:text-xs lg:flex-row lg:justify-start lg:gap-3 lg:px-4 lg:py-3 lg:text-left lg:text-[15px]",
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
                    <T k={label}/>
                  </Link>
                ) : (
                  <span className={cn(className, "cursor-default")} title={t("Em breve")} aria-disabled="true">
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
