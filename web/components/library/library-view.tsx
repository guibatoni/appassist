"use client"

import { useMemo, useState } from "react"
import { cards, libraryCardIds, type Attribute, type CardKind } from "@/lib/data"
import { LibraryToolbar, type Filters, type SortKey } from "./library-toolbar"
import { CardGrid } from "./card-grid"
import { CardDetail } from "./card-detail"

const rarityRank = { Comum: 0, Rara: 1, Épica: 2, Lendária: 3 }

export function LibraryView() {
  const [query, setQuery] = useState("")
  const [filters, setFilters] = useState<Filters>({ attribute: "Todos", kind: "Todos", category: "Todas" })
  const [sort, setSort] = useState<SortKey>("rarity")
  const [view, setView] = useState<"grid" | "list">("grid")
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState("c01")
  const [favorites, setFavorites] = useState<Set<string>>(() => new Set(["c01", "c06", "c21"]))
  const [marked, setMarked] = useState<Set<string>>(() => new Set(["c07"]))

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = cards
      .filter((c) => libraryCardIds.includes(c.id))
      .filter((c) => !q || c.name.toLowerCase().includes(q) || c.type.toLowerCase().includes(q))
      .filter((c) => filters.attribute === "Todos" || c.attribute === (filters.attribute as Attribute))
      .filter((c) => filters.kind === "Todos" || c.kind === (filters.kind as CardKind))
      .filter((c) => filters.category === "Todas" || c.category === filters.category)

    const sorters = {
      rarity: (a: (typeof cards)[number], b: (typeof cards)[number]) => rarityRank[b.rarity] - rarityRank[a.rarity] || b.atk - a.atk,
      atk: (a: (typeof cards)[number], b: (typeof cards)[number]) => b.atk - a.atk,
      name: (a: (typeof cards)[number], b: (typeof cards)[number]) => a.name.localeCompare(b.name, "pt-BR"),
    }
    return [...list].sort(sorters[sort])
  }, [query, filters, sort])

  const selected = cards.find((c) => c.id === selectedId) ?? cards[0]

  const toggle = (setter: typeof setFavorites) => (id: string) =>
    setter((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <section className="panel" aria-label="Coleção de cartas">
      <LibraryToolbar
        query={query}
        onQueryChange={setQuery}
        filters={filters}
        onFiltersChange={setFilters}
        sort={sort}
        onSortChange={setSort}
        view={view}
        onViewChange={setView}
        page={page}
        onPageChange={setPage}
        resultCount={visible.length}
      />
      <div className="grid gap-3 p-3 lg:gap-4 xl:grid-cols-[minmax(0,1fr)_480px]">
        <CardGrid
          cards={visible}
          view={view}
          selectedId={selected.id}
          favorites={favorites}
          onSelect={setSelectedId}
        />
        <CardDetail
          card={selected}
          isFavorite={favorites.has(selected.id)}
          isMarked={marked.has(selected.id)}
          onToggleFavorite={() => toggle(setFavorites)(selected.id)}
          onToggleMarked={() => toggle(setMarked)(selected.id)}
        />
      </div>
    </section>
  )
}
