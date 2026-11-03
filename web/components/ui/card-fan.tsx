import { cardById } from "@/lib/data"
import { GameCardArt } from "./game-card"

export function CardFan({ ids }: { ids: [string, string, string] }) {
  const [left, center, right] = ids.map(cardById)
  return (
    <div className="relative flex h-full items-center justify-center" aria-hidden="true">
      <div className="absolute inset-x-0 top-1/2 h-16 -translate-y-1/2 rounded-[50%] border-2 border-primary/50 shadow-[0_0_30px_rgb(56_200_255/0.6),inset_0_0_30px_rgb(56_200_255/0.4)]" />
      <div className="relative flex items-end">
        <GameCardArt card={left} size="md" className="w-20 -rotate-12 translate-x-3 translate-y-2" />
        <GameCardArt card={center} size="md" className="z-10 w-24 shadow-[0_0_24px_rgb(163_92_245/0.8)]" />
        <GameCardArt card={right} size="md" className="w-20 rotate-12 -translate-x-3 translate-y-2" />
      </div>
    </div>
  )
}
