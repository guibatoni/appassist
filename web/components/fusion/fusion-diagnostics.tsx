import { CircleCheck, Cpu, Info } from "lucide-react"
import { diagnostics } from "@/lib/data"
import { Panel } from "@/components/ui/panel"

export function FusionDiagnostics() {
  return (
    <Panel title="Diagnóstico da Fusão" icon={Cpu} action={<Info className="size-4 text-foreground/80" aria-label="Informações" />}>
      <ul className="flex flex-col gap-3 py-1 text-sm">
        {diagnostics.map((d) => (
          <li key={d.label} className="flex items-center gap-2 text-white">
            <CircleCheck className="size-5 text-success" aria-hidden="true" />
            {d.label}: <span className="font-medium text-success">{d.value}</span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
