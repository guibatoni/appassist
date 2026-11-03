import { BarChart3, Bug, Sparkles, Wand2 } from "lucide-react"
import { collectionStats } from "@/lib/data"
import { ProgressBar } from "@/components/ui/panel"
import { cn, formatNumber } from "@/lib/utils"

const icons = { Monstros: Bug, Magias: Wand2, Armadilhas: Sparkles }
const iconTones = { cyan: "text-gold", green: "text-success", purple: "text-violet" }

export function CollectionSummary({ className }: { className?: string }) {
  const { breakdown, owned, total } = collectionStats
  const percent = ((owned / total) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })

  return (
    <section className={cn("panel px-4 py-3", className)} aria-labelledby="resumo">
      <h2 id="resumo" className="flex items-center gap-2 font-display font-semibold text-white">
        <BarChart3 className="size-5 text-primary" aria-hidden="true" />
        Resumo da Coleção
      </h2>
      <ul className="mt-2 flex flex-col gap-1">
        {breakdown.map((b) => {
          const Icon = icons[b.label as keyof typeof icons]
          return (
            <li key={b.label} className="grid grid-cols-[1rem_5.5rem_3rem_1fr_3rem] items-center gap-2 text-xs">
              <Icon className={cn("size-3.5", iconTones[b.tone])} aria-hidden="true" />
              <span className="text-foreground/90">{b.label}</span>
              <span className="tabular-nums text-white">{formatNumber(b.count)}</span>
              <ProgressBar value={b.percent} tone={b.tone} className="h-1.5" />
              <span className="text-right tabular-nums text-foreground/90">{b.percent.toLocaleString("pt-BR")}%</span>
            </li>
          )
        })}
      </ul>
      <div className="mt-2 flex items-center justify-between border-t border-line/50 pt-2 text-sm">
        <span className="font-semibold text-white">Total</span>
        <span className="tabular-nums text-white">{formatNumber(owned)} / {formatNumber(total)}</span>
        <span className="font-semibold text-success">{percent}%</span>
      </div>
    </section>
  )
}
