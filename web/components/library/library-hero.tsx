import { Layers } from "lucide-react"
import { CardFan } from "@/components/ui/card-fan"

export function LibraryHero() {
  return (
    <section className="panel flex items-center justify-between gap-4 overflow-hidden px-5 py-4">
      <div>
        <h1 className="flex items-center gap-3 font-display text-2xl font-bold text-white sm:text-3xl">
          <Layers className="size-8 text-primary sm:size-10" aria-hidden="true" />
          Biblioteca de Cartas
        </h1>
        <p className="mt-2 text-sm text-foreground/80 sm:text-base">
          Explore, organize e gerencie toda a sua coleção de cartas.
        </p>
      </div>
      <div className="hidden h-28 w-80 shrink-0 md:block">
        <CardFan ids={["c01", "c07", "c03"]} />
      </div>
    </section>
  )
}
