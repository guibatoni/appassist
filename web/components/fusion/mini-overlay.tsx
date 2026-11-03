import { Swords } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { cn } from "@/lib/utils"

const duel = { playerLp: 8000, opponentLp: 7600, turn: 3 }
const opponentRow = [1, 1, 0, 1, 1]
const playerRow = [0, 1, 0, 1, 0]

function Slot({ filled, side }: { filled: boolean; side: "player" | "opponent" }) {
  return (
    <span
      className={cn(
        "aspect-[3/2] rounded-sm border",
        filled
          ? side === "opponent"
            ? "border-gold bg-gradient-to-b from-[#c2601e] to-[#5a2508] shadow-[0_0_8px_rgb(245_184_61/0.6)]"
            : "border-gold bg-gradient-to-b from-[#d9862a] to-[#6b3a08] shadow-[0_0_8px_rgb(245_184_61/0.6)]"
          : "border-primary/70 bg-primary/10 shadow-[inset_0_0_8px_rgb(56_200_255/0.4)]",
      )}
    />
  )
}

export function MiniOverlay() {
  return (
    <Panel title={<>Mini Overlay de Duelo <span className="text-sm font-normal text-foreground/80">(Prévia)</span></>} icon={Swords}>
      <div className="flex items-center justify-between">
        <p className="font-display text-xl font-bold text-primary"><span className="text-sm text-white">PV</span> {duel.playerLp}</p>
        <span className="rounded border border-primary/60 bg-primary/10 px-3 py-0.5 text-xs text-white [clip-path:polygon(8%_0,92%_0,100%_50%,92%_100%,8%_100%,0_50%)]">
          Turno {duel.turn}
        </span>
        <p className="font-display text-xl font-bold text-danger"><span className="text-sm text-white">PV</span> {duel.opponentLp}</p>
      </div>
      <div className="mt-2 rounded-md bg-gradient-to-b from-[#0a2a5a] to-[#06122b] p-2 [perspective:400px]" aria-label="Campo de duelo">
        <div className="grid gap-2 [transform:rotateX(35deg)]">
          <div className="grid grid-cols-5 gap-1.5">{opponentRow.map((f, i) => <Slot key={i} filled={!!f} side="opponent" />)}</div>
          <div className="grid grid-cols-5 gap-1.5">{playerRow.map((f, i) => <Slot key={i} filled={!!f} side="player" />)}</div>
        </div>
      </div>
    </Panel>
  )
}
