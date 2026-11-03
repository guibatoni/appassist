import type { Metadata } from "next"
import { FusionHeader } from "@/components/fusion/fusion-header"
import { FusionAnalysis } from "@/components/fusion/fusion-analysis"
import { AlternativeRoutes } from "@/components/fusion/alternative-routes"
import { RecommendedCombos } from "@/components/fusion/recommended-combos"
import { FusionHistory } from "@/components/fusion/fusion-history"
import { CardComparison } from "@/components/fusion/card-comparison"
import { MiniOverlay } from "@/components/fusion/mini-overlay"
import { FusionDiagnostics } from "@/components/fusion/fusion-diagnostics"

export const metadata: Metadata = {
  title: "Fusões — DUELTRACE",
}

export default function FusionPage() {
  return (
    <div className="flex flex-col gap-3 lg:gap-4">
      <FusionHeader />
      <FusionAnalysis />
      <div className="grid gap-3 lg:gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,0.95fr)_minmax(0,1fr)]">
        <AlternativeRoutes />
        <RecommendedCombos />
        <FusionHistory className="md:col-span-2 xl:col-span-1" />
      </div>
      <div className="grid gap-3 lg:gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.75fr)_minmax(0,0.6fr)]">
        <CardComparison className="md:col-span-2 xl:col-span-1" />
        <MiniOverlay />
        <FusionDiagnostics />
      </div>
    </div>
  )
}
