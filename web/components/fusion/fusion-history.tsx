import Link from "next/link"
import { ArrowRight, CircleCheck, History, Plus } from "lucide-react"
import { cardById, fusionHistory } from "@/lib/data"
import { GameCardArt } from "@/components/ui/game-card"
import { Panel } from "@/components/ui/panel"

export function FusionHistory({ className }: { className?: string }) {
  return (
    <Panel
      className={className}
      title={<>Histórico de Fusões <span className="text-sm font-normal text-foreground/80">(Recentes)</span></>}
      icon={History}
      action={
        <Link href="#" className="flex items-center gap-1 text-sm text-primary hover:underline">
          Ver Tudo <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      }
      bodyClassName="p-0 overflow-x-auto"
    >
      <table className="w-full min-w-[420px] text-sm">
        <thead>
          <tr className="border-b border-line/40 text-xs text-foreground/80">
            <th scope="col" className="px-3 py-1.5 text-left font-medium">Data</th>
            <th scope="col" className="px-2 py-1.5 text-left font-medium">Combinação</th>
            <th scope="col" className="px-2 py-1.5 text-left font-medium">Resultado</th>
            <th scope="col" className="px-3 py-1.5 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line/30">
          {fusionHistory.map((h) => {
            const result = cardById(h.result)
            return (
              <tr key={h.id} className="transition-colors hover:bg-primary/5">
                <td className="whitespace-nowrap px-3 py-1.5 text-xs text-white">{h.date}</td>
                <td className="px-2 py-1.5">
                  <span className="flex items-center gap-1">
                    <GameCardArt card={cardById(h.inputs[0])} size="xs" className="w-7" />
                    <Plus className="size-3 text-white" aria-hidden="true" />
                    <GameCardArt card={cardById(h.inputs[1])} size="xs" className="w-7" />
                  </span>
                </td>
                <td className="px-2 py-1.5">
                  <span className="flex items-center gap-2 text-xs text-white">
                    <GameCardArt card={result} size="xs" className="w-7" />
                    {result.name}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right">
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                    <CircleCheck className="size-4" aria-hidden="true" /> {h.status}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Panel>
  )
}
