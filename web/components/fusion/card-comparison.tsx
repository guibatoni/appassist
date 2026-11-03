import { Fragment } from "react"
import { Scale } from "lucide-react"
import { cardById, comparisonIds } from "@/lib/data"
import { AttributeIcon, GameCardArt } from "@/components/ui/game-card"
import { Panel } from "@/components/ui/panel"
import { cn } from "@/lib/utils"

export function CardComparison({ className }: { className?: string }) {
  const compared = comparisonIds.map(cardById)
  const maxAtk = Math.max(...compared.map((c) => c.atk))
  const minDef = Math.min(...compared.map((c) => c.def))
  const rows = [
    { label: "ATK", render: (c: (typeof compared)[number]) => <span className={cn(c.atk === maxAtk && "font-semibold text-success")}>{c.atk}</span> },
    { label: "DEF", render: (c: (typeof compared)[number]) => <span className={cn(c.def !== minDef && c === compared[0] && "font-semibold text-success")}>{c.def}</span> },
    { label: "Nível", render: (c: (typeof compared)[number]) => c.level },
    { label: "Atributo", render: (c: (typeof compared)[number]) => <span className="inline-flex items-center gap-1"><AttributeIcon attribute={c.attribute} className="size-4" />{c.attribute}</span> },
  ]

  return (
    <Panel className={className} title="Comparação de Cartas" icon={Scale}>
      <div className="flex flex-col gap-3 md:flex-row">
        <div className="flex items-center justify-center gap-2">
          {compared.map((card, i) => (
            <Fragment key={card.id}>
              {i > 0 && <span className="font-display text-lg font-bold italic text-foreground/80">VS</span>}
              <figure className={cn("w-24 rounded-lg p-1 text-center", i === 0 && "ring-1 ring-gold shadow-[0_0_14px_rgb(245_184_61/0.45)]")}>
                <GameCardArt card={card} />
                <figcaption className="mt-1 text-[11px] leading-tight text-white">{card.name}</figcaption>
              </figure>
            </Fragment>
          ))}
        </div>
        <div className="min-w-0 flex-1 overflow-x-auto rounded-md border border-line/50">
          <table className="w-full min-w-[320px] text-center text-sm">
            <thead>
              <tr className="border-b border-line/40 text-[11px] leading-tight text-foreground/90">
                <th scope="col" className="px-2 py-1.5 text-left font-medium">Atributo</th>
                {compared.map((c) => (
                  <th key={c.id} scope="col" className="px-2 py-1.5 font-medium">
                    <span className="inline-flex items-center gap-1"><AttributeIcon attribute={c.attribute} className="size-3.5 shrink-0" />{c.name}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line/30 text-white">
              {rows.map((r) => (
                <tr key={r.label}>
                  <th scope="row" className="px-2 py-1.5 text-left font-normal text-foreground/90">{r.label}</th>
                  {compared.map((c) => (
                    <td key={c.id} className="px-2 py-1.5 tabular-nums">{r.render(c)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  )
}
