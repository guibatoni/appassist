"use client"

import type { GameCard } from "@/lib/data"
import { AttributeIcon, GameCardArt } from "@/components/ui/game-card"
import { cn, formatNumber } from "@/lib/utils"

type Props = {
  cards: GameCard[]
  view: "grid" | "list"
  selectedId: string
  favorites: Set<string>
  onSelect: (id: string) => void
}

export function CardGrid({ cards, view, selectedId, favorites, onSelect }: Props) {
  if (cards.length === 0) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-lg border border-dashed border-line text-sm text-muted">
        Nenhuma carta encontrada com esses filtros.
      </div>
    )
  }

  return (
    <div className="max-h-[440px] overflow-y-auto pr-2 scrollbar-thin xl:max-h-[392px]">
      {view === "grid" ? (
        <ul className="grid grid-cols-3 gap-2.5 sm:grid-cols-5 lg:grid-cols-7">
          {cards.map((card) => (
            <li key={card.id}>
              <button
                type="button"
                onClick={() => onSelect(card.id)}
                aria-pressed={selectedId === card.id}
                aria-label={card.name}
                className="block w-full rounded-lg transition-transform duration-200 hover:-translate-y-1 hover:drop-shadow-[0_0_12px_rgb(56_200_255/0.55)] focus-visible:outline-2 focus-visible:outline-primary"
              >
                <GameCardArt card={card} selected={selectedId === card.id} favorite={favorites.has(card.id)} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {cards.map((card) => (
            <li key={card.id}>
              <button
                type="button"
                onClick={() => onSelect(card.id)}
                aria-pressed={selectedId === card.id}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg border px-2 py-1.5 text-left text-sm transition-all",
                  selectedId === card.id ? "border-primary bg-primary/10 shadow-[0_0_12px_rgb(56_200_255/0.35)]" : "border-line/50 hover:border-primary/60 hover:bg-primary/5",
                )}
              >
                <GameCardArt card={card} size="xs" />
                <span className="flex-1 truncate font-medium text-white">{card.name}</span>
                <span className="hidden items-center gap-1 text-foreground/80 sm:flex">
                  <AttributeIcon attribute={card.attribute} className="size-4" />
                  {card.attribute}
                </span>
                <span className="hidden w-24 text-foreground/80 md:block">{card.type}</span>
                <span className="w-24 text-right tabular-nums text-foreground/90">
                  {card.kind === "Monstro" ? `${formatNumber(card.atk)} / ${formatNumber(card.def)}` : card.kind}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
