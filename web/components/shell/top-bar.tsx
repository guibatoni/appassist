import { Bell, CircleHelp, Minus, Square, X } from "lucide-react"

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 48 44" className="h-9 w-10 sm:h-11 sm:w-12" aria-hidden="true">
        <defs>
          <linearGradient id="logo-g" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#7fe3ff" />
            <stop offset="1" stopColor="#1a8fe0" />
          </linearGradient>
        </defs>
        <path d="M2 2h44L24 42z" fill="none" stroke="url(#logo-g)" strokeWidth="4" strokeLinejoin="round" />
        <path d="M13 9h22L24 30z" fill="none" stroke="url(#logo-g)" strokeWidth="3" strokeLinejoin="round" />
      </svg>
      <div className="leading-none">
        <p className="font-display text-2xl font-extrabold italic tracking-wide text-transparent bg-clip-text bg-gradient-to-b from-white to-[#b9cbe6] sm:text-3xl">
          DUELTRACE
        </p>
        <p className="mt-1 flex items-center gap-2 font-display text-xs italic text-gold sm:text-sm">
          <span className="h-px w-5 bg-gold/70" aria-hidden="true" />
          MultiMod Companion
          <span className="h-px w-5 bg-gold/70" aria-hidden="true" />
        </p>
      </div>
    </div>
  )
}

export function TopBar() {
  return (
    <header className="flex items-center justify-between gap-4 px-4 pb-3 pt-4 sm:px-6 lg:px-8 lg:pt-5">
      <Logo />
      <div className="flex items-center gap-2 sm:gap-4">
        <div className="hidden items-center gap-2 rounded-md border border-success/30 bg-success/10 px-3 py-1.5 sm:flex">
          <span className="relative flex size-3 items-center justify-center">
            <span className="absolute size-3 animate-ping rounded-full bg-success/40" />
            <span className="size-2.5 rounded-full border-2 border-success" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-success">Sistema OK</p>
            <p className="text-[10px] text-muted">v1.0.0</p>
          </div>
        </div>
        <button type="button" className="relative rounded-md p-2 text-foreground/80 transition-colors hover:bg-primary/10 hover:text-primary" aria-label="Notificações">
          <Bell className="size-5" />
          <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-gold" />
        </button>
        <button type="button" className="rounded-md p-2 text-foreground/80 transition-colors hover:bg-primary/10 hover:text-primary" aria-label="Ajuda">
          <CircleHelp className="size-5" />
        </button>
        <div className="hidden items-center gap-1 pl-2 md:flex" aria-hidden="true">
          <span className="p-2 text-foreground/70"><Minus className="size-4" /></span>
          <span className="p-2 text-foreground/70"><Square className="size-3.5" /></span>
          <span className="p-2 text-foreground/70"><X className="size-4" /></span>
        </div>
      </div>
    </header>
  )
}
