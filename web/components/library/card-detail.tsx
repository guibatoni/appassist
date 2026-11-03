"use client"

import { Bookmark, ChevronDown, FileText, LayoutList, MoreHorizontal, Shapes, Shield, Star, Swords, Tag } from "lucide-react"
import type { GameCard } from "@/lib/data"
import { AttributeIcon, GameCardArt, StarRow } from "@/components/ui/game-card"
import { Pill } from "@/components/ui/panel"
import { cn } from "@/lib/utils"

type Props = {
  card: GameCard
  isFavorite: boolean
  isMarked: boolean
  onToggleFavorite: () => void
  onToggleMarked: () => void
}

export function CardDetail({ card, isFavorite, isMarked, onToggleFavorite, onToggleMarked }: Props) {
  const rarityTone = card.rarity === "Lendária" ? "violet" : card.rarity === "Épica" ? "gold" : "muted"
  const rows = [
    { icon: <AttributeIcon attribute={card.attribute} className="size-4" />, label: "Atributo", value: card.attribute },
    { icon: <Shapes className="size-4 text-foreground/80" aria-hidden="true" />, label: "Tipo", value: card.type },
    { icon: <Tag className="size-4 text-foreground/80" aria-hidden="true" />, label: "Categoria", value: card.category },
  ]

  return (
    <aside className="rounded-xl border border-line/70 bg-[#06122b]/80 p-3" aria-label={`Detalhes de ${card.name}`}>
      <div className="flex gap-3">
        <div className="w-28 shrink-0 sm:w-32">
          <div className="mb-1 flex justify-start pl-1 text-[10px]"><StarRow count={card.stars - 1} /></div>
          <GameCardArt card={card} size="lg" className="ring-2 ring-gold/80 shadow-[0_0_18px_rgb(245_184_61/0.5)]" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-display text-xl font-bold italic text-white sm:text-2xl">{card.name}</h3>
            <div className="flex shrink-0 items-center gap-1">
              <button type="button" onClick={onToggleFavorite} aria-pressed={isFavorite} aria-label="Favoritar" className="rounded p-1 transition-colors hover:bg-gold/10">
                <Star className={cn("size-6", isFavorite ? "fill-gold text-gold" : "text-gold")} />
              </button>
              <button type="button" onClick={onToggleMarked} aria-pressed={isMarked} aria-label="Marcar" className="rounded p-1 transition-colors hover:bg-primary/10">
                <Bookmark className={cn("size-6 text-white", isMarked && "fill-white")} />
              </button>
              <button type="button" aria-label="Mais opções" className="rounded p-1 text-white hover:bg-primary/10">
                <MoreHorizontal className="size-6" />
              </button>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap gap-2">
            <Pill tone="gold" className="-skew-x-12 px-4"><span className="skew-x-12">{card.kind}</span></Pill>
            <Pill tone={rarityTone} className="-skew-x-12 px-4"><span className="skew-x-12">{card.rarity}</span></Pill>
          </div>

          <dl className="mt-2 divide-y divide-line/40 text-sm">
            {rows.map((r) => (
              <div key={r.label} className="flex items-center gap-2 py-1.5">
                {r.icon}
                <dt className="text-foreground/85">{r.label}:</dt>
                <dd className="text-white">{r.value}</dd>
              </div>
            ))}
          </dl>

          {card.kind === "Monstro" && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <div className="flex items-center justify-center gap-2 rounded-md border border-primary/50 bg-primary/10 px-2 py-1.5">
                <Swords className="size-5 text-foreground/90" aria-hidden="true" />
                <span className="text-sm text-foreground/90">ATK</span>
                <span className="font-display text-xl font-bold text-primary sm:text-2xl">{card.atk}</span>
              </div>
              <div className="flex items-center justify-center gap-2 rounded-md border border-danger/60 bg-danger/10 px-2 py-1.5">
                <Shield className="size-5 text-danger" aria-hidden="true" />
                <span className="text-sm text-foreground/90">DEF</span>
                <span className="font-display text-xl font-bold text-[#ff6b73] sm:text-2xl">{card.def}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-line/70 bg-panel/60">
        <h4 className="flex items-center gap-2 border-b border-line/50 px-3 py-2 font-display text-sm font-semibold text-white">
          <FileText className="size-4 text-primary" aria-hidden="true" />
          Efeito da Carta
        </h4>
        <p className="m-2 rounded-md border border-line/40 bg-[#040b1f]/70 px-3 py-2.5 text-[15px] italic leading-relaxed text-foreground/95">
          {card.effect}
        </p>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_1.4fr]">
        <button type="button" onClick={onToggleFavorite} className="btn-gold">
          <Star className="size-5 fill-gold" aria-hidden="true" />
          {isFavorite ? "Favoritada" : "Favorita"}
        </button>
        <button type="button" onClick={onToggleMarked} className="btn-ghost">
          <Bookmark className={cn("size-5", isMarked && "fill-white")} aria-hidden="true" />
          {isMarked ? "Marcada" : "Marcar"}
        </button>
        <button type="button" className="btn-ghost col-span-2 sm:col-span-1">
          <LayoutList className="size-5" aria-hidden="true" />
          Adicionar ao Deck
          <ChevronDown className="size-4" aria-hidden="true" />
        </button>
      </div>
    </aside>
  )
}
