import { Bookmark, Layers, Sparkles, Star } from "lucide-react"
import { collectionStats } from "@/lib/data"
import { formatNumber } from "@/lib/utils"
import { ProgressBar } from "@/components/ui/panel"

export function CollectionCard() {
  const { owned, total, favorites, marked, newCards } = collectionStats
  const percent = Math.round((owned / total) * 1000) / 10
  const stats = [
    { label: "Favoritas", value: favorites, icon: Star },
    { label: "Marcadas", value: marked, icon: Bookmark },
    { label: "Novas", value: newCards, icon: Sparkles, dot: true },
  ]

  return (
    <section className="panel px-5 py-4" aria-labelledby="minha-colecao">
      <div className="flex items-start gap-3">
        <Layers className="mt-0.5 size-6 text-primary" aria-hidden="true" />
        <div className="flex-1">
          <h2 id="minha-colecao" className="font-display font-semibold text-white">Minha Coleção</h2>
          <div className="flex items-baseline justify-between">
            <p className="font-display text-xl font-bold text-primary">
              {formatNumber(owned)} <span className="text-base font-medium text-foreground/80">/ {formatNumber(total)}</span>
            </p>
            <span className="text-sm font-semibold text-success">({percent.toLocaleString("pt-BR")}%)</span>
          </div>
        </div>
      </div>
      <ProgressBar value={percent} tone="green" segmented className="mt-2 h-2.5" />
      <dl className="mt-3 grid grid-cols-3 divide-x divide-line/60">
        {stats.map(({ label, value, icon: Icon, dot }) => (
          <div key={label} className="flex items-center gap-2 px-2 first:pl-0">
            <Icon className="size-5 shrink-0 text-foreground/80" aria-hidden="true" />
            <div className="leading-tight">
              <dt className="flex items-center gap-1 text-[11px] text-muted">
                {label}
                {dot && <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />}
              </dt>
              <dd className="text-sm font-semibold text-white">{value}</dd>
            </div>
          </div>
        ))}
      </dl>
    </section>
  )
}
