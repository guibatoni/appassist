"use client"

import { useState } from "react"
import { FlaskConical, GitBranch, History, Infinity as InfinityIcon, Scale, Star } from "lucide-react"
import { CardFan } from "@/components/ui/card-fan"
import { cn } from "@/lib/utils"

const tabs = [
  { id: "analise", label: "Análise de Fusão", icon: FlaskConical },
  { id: "rotas", label: "Rotas de Fusão", icon: GitBranch },
  { id: "combos", label: "Combinações Recomendadas", icon: Star },
  { id: "historico", label: "Histórico de Fusões", icon: History },
  { id: "comparador", label: "Comparador de Cartas", icon: Scale },
]

export function FusionHeader() {
  const [active, setActive] = useState("analise")

  return (
    <section className="panel flex items-center gap-4 overflow-hidden px-5 py-3">
      <div className="min-w-0 flex-1">
        <h1 className="flex items-center gap-3 font-display text-2xl font-bold italic text-white sm:text-3xl">
          <InfinityIcon className="size-9 text-gold" aria-hidden="true" />
          Fusões
        </h1>
        <p className="mt-1 text-sm text-foreground/85">
          Analise combinações, rotas de fusão, chances de sucesso e descubra as melhores formas de invocar cartas poderosas.
        </p>
        <div role="tablist" aria-label="Seções de fusão" className="mt-3 flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={active === id}
              onClick={() => setActive(id)}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-md border px-4 py-2 text-sm transition-all",
                active === id
                  ? "border-primary bg-gradient-to-b from-primary/35 to-primary/10 font-semibold text-white shadow-[0_0_16px_rgb(56_200_255/0.45)]"
                  : "border-line bg-panel-strong/60 text-foreground/90 hover:border-primary/60 hover:text-white",
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="hidden h-28 w-72 shrink-0 xl:block">
        <CardFan ids={["c01", "c07", "c03"]} />
      </div>
    </section>
  )
}
