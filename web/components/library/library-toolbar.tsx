"use client"

import { ChevronDown, ChevronLeft, ChevronRight, Filter, LayoutGrid, List, Search, SlidersHorizontal, X } from "lucide-react"
import { attributes, cardKinds, categories, collectionStats } from "@/lib/data"
import { cn, formatNumber } from "@/lib/utils"

export type Filters = { attribute: string; kind: string; category: string }
export type SortKey = "rarity" | "atk" | "name"

const sortOptions: { value: SortKey; label: string }[] = [
  { value: "rarity", label: "Raridade (Maior → Menor)" },
  { value: "atk", label: "ATK (Maior → Menor)" },
  { value: "name", label: "Nome (A → Z)" },
]

type Props = {
  query: string
  onQueryChange: (v: string) => void
  filters: Filters
  onFiltersChange: (f: Filters) => void
  sort: SortKey
  onSortChange: (s: SortKey) => void
  view: "grid" | "list"
  onViewChange: (v: "grid" | "list") => void
  page: number
  onPageChange: (p: number) => void
  resultCount: number
}

function SelectField({ label, value, options, onChange, className }: { label: string; value: string; options: string[]; onChange: (v: string) => void; className?: string }) {
  return (
    <label className={cn("field relative flex items-center gap-1.5 px-3 py-1.5", className)}>
      <span className="shrink-0 text-foreground/80">{label}:</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full cursor-pointer appearance-none bg-transparent pr-5 text-white outline-none [&>option]:bg-panel"
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 size-4 text-foreground/70" aria-hidden="true" />
    </label>
  )
}

export function LibraryToolbar(props: Props) {
  const { query, onQueryChange, filters, onFiltersChange, sort, onSortChange, view, onViewChange, page, onPageChange, resultCount } = props
  const pages = [1, 2, 3, 4, 5]
  const isFiltered = query || filters.attribute !== "Todos" || filters.kind !== "Todos" || filters.category !== "Todas"
  const displayCount = isFiltered ? resultCount : collectionStats.owned

  return (
    <div className="flex flex-col gap-2.5 border-b border-line/50 p-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <label className="field flex min-w-0 flex-1 basis-72 items-center gap-2 px-3 py-2">
          <Search className="size-5 shrink-0 text-foreground/80" aria-hidden="true" />
          <span className="sr-only">Buscar carta</span>
          <input
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Buscar carta..."
            className="min-w-0 flex-1 bg-transparent text-white outline-none placeholder:text-foreground/60"
          />
          <kbd className="hidden rounded border border-line bg-panel-strong px-1.5 py-0.5 text-[11px] text-foreground/80 sm:inline">Ctrl + K</kbd>
        </label>

        <button type="button" className="btn-ghost border-primary/60 py-2 font-semibold">
          <Filter className="size-4 text-primary" aria-hidden="true" />
          Filtros Avançados
          <ChevronDown className="size-4" aria-hidden="true" />
        </button>

        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-foreground/80 md:inline">Ordenar por:</span>
          <label className="field relative flex items-center px-3 py-2">
            <span className="sr-only">Ordenar por</span>
            <select
              value={sort}
              onChange={(e) => onSortChange(e.target.value as SortKey)}
              className="cursor-pointer appearance-none bg-transparent pr-7 text-white outline-none [&>option]:bg-panel"
            >
              {sortOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 size-4 text-foreground/70" aria-hidden="true" />
          </label>
        </div>

        <div className="flex items-center gap-1 rounded-md border border-line bg-[#06102a]/90 p-1" role="group" aria-label="Modo de visualização">
          {([["grid", LayoutGrid, "Grade"], ["list", List, "Lista"]] as const).map(([v, Icon, label]) => (
            <button
              key={v}
              type="button"
              onClick={() => onViewChange(v)}
              aria-pressed={view === v}
              aria-label={label}
              className={cn(
                "rounded px-2 py-1 transition-all",
                view === v ? "bg-primary/25 text-primary shadow-[0_0_10px_rgb(56_200_255/0.5)] ring-1 ring-primary" : "text-foreground/80 hover:text-white",
              )}
            >
              <Icon className="size-5" />
            </button>
          ))}
        </div>
        <button type="button" className="btn-ghost px-2.5" aria-label="Ajustes de exibição">
          <SlidersHorizontal className="size-5" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 text-sm">
        <SelectField label="Atributo" value={filters.attribute} options={["Todos", ...attributes]} onChange={(attribute) => onFiltersChange({ ...filters, attribute })} className="w-40" />
        <SelectField label="Tipo" value={filters.kind} options={["Todos", ...cardKinds]} onChange={(kind) => onFiltersChange({ ...filters, kind })} className="w-40" />
        <SelectField label="Categoria" value={filters.category} options={["Todas", ...categories]} onChange={(category) => onFiltersChange({ ...filters, category })} className="w-44" />
        <button
          type="button"
          onClick={() => {
            onFiltersChange({ attribute: "Todos", kind: "Todos", category: "Todas" })
            onQueryChange("")
          }}
          className="flex items-center gap-1.5 px-2 py-1.5 text-foreground/90 transition-colors hover:text-primary"
        >
          <X className="size-4" aria-hidden="true" />
          Limpar Filtros
        </button>

        <p className="ml-auto text-foreground/90" aria-live="polite">Exibindo {formatNumber(displayCount)} cartas</p>

        <nav aria-label="Paginação" className="flex items-center gap-1">
          <button type="button" onClick={() => onPageChange(Math.max(1, page - 1))} className="rounded p-1 text-foreground/80 hover:text-primary" aria-label="Página anterior">
            <ChevronLeft className="size-4" />
          </button>
          {pages.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              aria-current={page === p ? "page" : undefined}
              className={cn(
                "min-w-7 rounded px-1.5 py-0.5 transition-all",
                page === p ? "bg-primary/25 text-white ring-1 ring-primary shadow-[0_0_10px_rgb(56_200_255/0.5)]" : "text-foreground/80 hover:text-white",
              )}
            >
              {p}
            </button>
          ))}
          <span className="px-1 text-foreground/60">…</span>
          <button type="button" onClick={() => onPageChange(collectionStats.totalPages)} className={cn("min-w-7 rounded px-1.5 py-0.5", page === collectionStats.totalPages ? "bg-primary/25 text-white ring-1 ring-primary" : "text-foreground/80 hover:text-white")}>
            {collectionStats.totalPages}
          </button>
          <button type="button" onClick={() => onPageChange(Math.min(collectionStats.totalPages, page + 1))} className="rounded p-1 text-foreground/80 hover:text-primary" aria-label="Próxima página">
            <ChevronRight className="size-4" />
          </button>
        </nav>
      </div>
    </div>
  )
}
