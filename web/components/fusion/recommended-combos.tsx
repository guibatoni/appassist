import { Crown, Plus, Star } from "lucide-react"
import { cardById, recommendedCombos } from "@/lib/data"
import { GameCardArt } from "@/components/ui/game-card"
import { Panel, Pill } from "@/components/ui/panel"

export function RecommendedCombos() {
  return (
    <Panel title="Combinações Recomendadas" icon={Star} bodyClassName="p-0">
      <ul className="divide-y divide-line/40">
        {recommendedCombos.map((combo) => (
          <li key={combo.id} className="flex items-center gap-2 px-3 py-1.5 transition-colors hover:bg-primary/5">
            <GameCardArt card={cardById(combo.inputs[0])} size="xs" className="w-10" />
            <Plus className="size-4 text-white" aria-hidden="true" />
            <GameCardArt card={cardById(combo.inputs[1])} size="xs" className="w-10" />
            <div className="ml-2 min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{cardById(combo.result).name}</p>
              <Pill tone={combo.tone} className="mt-0.5 text-[10px]">
                <Crown className="size-3" aria-hidden="true" /> {combo.tag}
              </Pill>
            </div>
            <span className={combo.tone === "gold" ? "font-display text-lg font-bold text-success" : "font-display text-lg font-semibold text-white"}>
              {combo.chance}%
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
