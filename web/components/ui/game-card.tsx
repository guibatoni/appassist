import Image from "next/image"
import { Droplet, Flame, Moon, Mountain, Star, Sun, Wind, type LucideIcon } from "lucide-react"
import type { Attribute, GameCard } from "@/lib/data"
import { cn } from "@/lib/utils"

export const attributeStyles: Record<Attribute, { icon: LucideIcon; frame: string; text: string }> = {
  Água: { icon: Droplet, frame: "from-[#6fd3ff] via-[#1d6fd6] to-[#0a2c6b]", text: "text-[#5cc8ff]" },
  Fogo: { icon: Flame, frame: "from-[#ffb36b] via-[#e2481f] to-[#6b1509]", text: "text-[#ff7a45]" },
  Terra: { icon: Mountain, frame: "from-[#ffe08a] via-[#c58a1e] to-[#5a3a08]", text: "text-[#f5b83d]" },
  Vento: { icon: Wind, frame: "from-[#a6ff9a] via-[#2aa84a] to-[#0b4a1d]", text: "text-[#4fe27a]" },
  Sombra: { icon: Moon, frame: "from-[#e0a6ff] via-[#8a3fe0] to-[#2d0b5e]", text: "text-[#c27dff]" },
  Luz: { icon: Sun, frame: "from-[#fff3b0] via-[#f0b43a] to-[#7a4a06]", text: "text-[#ffd45c]" },
}

export function AttributeIcon({ attribute, className }: { attribute: Attribute; className?: string }) {
  const { icon: Icon, text } = attributeStyles[attribute]
  return <Icon className={cn(text, className)} aria-hidden="true" />
}

export function StarRow({ count, className }: { count: number; className?: string }) {
  return (
    <span className={cn("flex items-center justify-center gap-px", className)} aria-label={`${count} estrelas`}>
      {Array.from({ length: count }).map((_, i) => (
        <Star key={i} className="size-[1em] fill-gold text-[#7a4a06]" strokeWidth={1.5} aria-hidden="true" />
      ))}
    </span>
  )
}

type GameCardProps = {
  card: GameCard
  size?: "xs" | "sm" | "md" | "lg"
  selected?: boolean
  favorite?: boolean
  className?: string
}

const sizeClasses = {
  xs: { root: "w-9 p-[2px] rounded-[4px]", stars: "hidden", icon: "hidden" },
  sm: { root: "w-14 p-[3px] rounded-md", stars: "text-[6px] py-0.5", icon: "hidden" },
  md: { root: "w-full p-[3px] rounded-lg", stars: "text-[10px] sm:text-xs py-1", icon: "size-4 sm:size-5" },
  lg: { root: "w-full p-1 rounded-lg", stars: "text-sm sm:text-base py-1.5", icon: "size-5" },
}

export function GameCardArt({ card, size = "md", selected, favorite, className }: GameCardProps) {
  const s = sizeClasses[size]
  const { icon: Icon, frame } = attributeStyles[card.attribute]

  return (
    <div
      className={cn(
        "relative bg-gradient-to-b shadow-[0_4px_14px_rgb(0_0_0/0.5)]",
        frame,
        s.root,
        selected && "ring-2 ring-primary ring-offset-2 ring-offset-[#040b1f] shadow-[0_0_22px_rgb(56_200_255/0.8)]",
        className,
      )}
    >
      <div className="relative aspect-[4/5] overflow-hidden rounded-[inherit] bg-black">
        <Image src={card.image || "/placeholder.svg"} alt={card.name} fill sizes="(max-width: 768px) 30vw, 160px" className="object-cover" />
        {size !== "xs" && size !== "sm" && (
          <span className="absolute left-1 top-1 flex size-6 items-center justify-center rounded-full border border-white/40 bg-black/55 backdrop-blur sm:size-7">
            <Icon className={cn("text-white", s.icon)} aria-hidden="true" />
          </span>
        )}
        {favorite && size !== "xs" && size !== "sm" && (
          <span className="absolute right-1 top-1 flex size-6 items-center justify-center rounded-full border border-gold/70 bg-black/55 sm:size-7">
            <Star className="size-3.5 fill-gold text-gold" aria-label="Favorita" />
          </span>
        )}
      </div>
      {size !== "xs" && (
        <div className={cn("mt-[2px] rounded-b-[inherit] bg-gradient-to-b from-[#1a1206] to-black/90", s.stars)}>
          <StarRow count={card.stars} />
        </div>
      )}
    </div>
  )
}
