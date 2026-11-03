import Link from "next/link"
import { Download, Infinity as InfinityIcon, Layers, Scale, Upload, Zap } from "lucide-react"

const actions = [
  { label: "Criar Deck", icon: Layers, href: "#" },
  { label: "Comparar Cartas", icon: Scale, href: "/fusoes" },
  { label: "Ver Fusões", icon: InfinityIcon, href: "/fusoes" },
  { label: "Exportar Lista", icon: Download, href: "#" },
  { label: "Importar Cartas", icon: Upload, href: "#" },
]

export function QuickActions() {
  return (
    <section className="panel px-4 py-3" aria-labelledby="acoes-rapidas">
      <h2 id="acoes-rapidas" className="flex items-center gap-2 font-display font-semibold text-white">
        <Zap className="size-5 text-primary" aria-hidden="true" />
        Ações Rápidas
      </h2>
      <ul className="mt-2.5 grid grid-cols-5 gap-2">
        {actions.map(({ label, icon: Icon, href }) => (
          <li key={label}>
            <Link
              href={href}
              className="flex h-full flex-col items-center justify-center gap-1.5 rounded-lg border border-line bg-panel-strong/70 px-1 py-3 text-center text-[11px] leading-tight text-foreground/95 transition-all hover:-translate-y-0.5 hover:border-primary hover:bg-primary/10 hover:shadow-[0_0_16px_rgb(56_200_255/0.4)] sm:text-xs"
            >
              <Icon className="size-7 text-foreground" strokeWidth={1.5} aria-hidden="true" />
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
