import { ChevronLeft, ChevronRight, Clock } from "lucide-react"
import { cardById, recentCardIds } from "@/lib/data"
import { GameCardArt } from "@/components/ui/game-card"

export function RecentCards() {
  return (
    <section className="panel px-4 py-3" aria-labelledby="recentes">
      <div className="flex items-center gap-2">
        <Clock className="size-6 text-primary" aria-hidden="true" />
        <div className="leading-tight">
          <h2 id="recentes" className="font-display font-semibold text-white">Cartas Recentes</h2>
          <p className="text-xs text-muted">Últimas cartas visualizadas</p>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button type="button" className="shrink-0 rounded-full border border-line p-1 text-foreground/80 hover:border-primary hover:text-primary" aria-label="Anteriores">
          <ChevronLeft className="size-4" />
        </button>
        <ul className="grid flex-1 grid-cols-5 gap-2">
          {recentCardIds.map((id) => {
            const card = cardById(id)
            return (
              <li key={id}>
                <GameCardArt card={card} size="md" className="transition-transform hover:-translate-y-0.5 [&_.aspect-\[4\/5\]]:aspect-[5/4]" />
              </li>
            )
          })}
        </ul>
        <button type="button" className="shrink-0 rounded-full border border-line p-1 text-foreground/80 hover:border-primary hover:text-primary" aria-label="Próximas">
          <ChevronRight className="size-4" />
        </button>
      </div>
    </section>
  )
}
