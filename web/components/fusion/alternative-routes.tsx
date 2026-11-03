"use client"

import { useState } from "react"
import { ArrowRight, Crown, Info, Network, Orbit, Plus, Star } from "lucide-react"
import { alternativeRoutes, cardById } from "@/lib/data"
import { GameCardArt } from "@/components/ui/game-card"
import { Panel } from "@/components/ui/panel"
import { cn } from "@/lib/utils"

const routeIcons = [Crown, Orbit, Star]

export function FusionTrio({ inputs, result }: { inputs: [string, string]; result: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <GameCardArt card={cardById(inputs[0])} size="xs" />
      <Plus className="size-3 text-white" aria-hidden="true" />
      <GameCardArt card={cardById(inputs[1])} size="xs" />
      <ArrowRight className="mx-1 size-4 text-white" aria-hidden="true" />
      <GameCardArt card={cardById(result)} size="xs" />
    </span>
  )
}

export function AlternativeRoutes() {
  const [selected, setSelected] = useState(alternativeRoutes[0].id)

  return (
    <Panel
      title={`Rotas Alternativas (${alternativeRoutes.length})`}
      icon={Network}
      action={<Info className="size-4 text-primary" aria-label="Informações" />}
    >
      <ul className="flex flex-col gap-1.5">
        {alternativeRoutes.map((route, i) => {
          const Icon = routeIcons[i]
          const active = selected === route.id
          return (
            <li key={route.id}>
              <button
                type="button"
                onClick={() => setSelected(route.id)}
                aria-pressed={active}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md border px-3 py-1.5 text-sm transition-all",
                  active
                    ? "border-gold bg-gradient-to-r from-gold/25 to-gold/5 text-gold shadow-[0_0_14px_rgb(245_184_61/0.35)]"
                    : "border-line/50 text-white hover:border-primary/60 hover:bg-primary/5",
                )}
              >
                <Icon className={cn("size-4", active ? "fill-gold text-gold" : "text-foreground/80")} aria-hidden="true" />
                <span className="w-28 text-left font-medium">{route.label}</span>
                <FusionTrio inputs={route.inputs} result={route.result} />
                <span className="ml-auto font-display font-semibold">{route.chance}%</span>
              </button>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
