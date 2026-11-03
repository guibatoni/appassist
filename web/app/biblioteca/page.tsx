import type { Metadata } from "next"
import { LibraryHero } from "@/components/library/library-hero"
import { CollectionCard } from "@/components/library/collection-card"
import { LibraryView } from "@/components/library/library-view"
import { RecentCards } from "@/components/library/recent-cards"
import { QuickActions } from "@/components/library/quick-actions"
import { CollectionSummary } from "@/components/library/collection-summary"

export const metadata: Metadata = {
  title: "Biblioteca de Cartas — DUELTRACE",
}

export default function LibraryPage() {
  return (
    <div className="flex flex-col gap-3 lg:gap-4">
      <div className="grid gap-3 lg:gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <LibraryHero />
        <CollectionCard />
      </div>
      <LibraryView />
      <div className="grid gap-3 lg:gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_minmax(0,1fr)]">
        <RecentCards />
        <QuickActions />
        <CollectionSummary className="md:col-span-2 xl:col-span-1" />
      </div>
    </div>
  )
}
