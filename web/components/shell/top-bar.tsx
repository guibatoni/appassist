import { ShieldCheck } from "lucide-react"
import { UpdateChecker } from "./update-checker"
import { WindowControls } from "./window-controls"

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
    <header className="sticky top-0 z-[60] flex items-center justify-between gap-3 rounded-t-2xl border-b border-line/40 bg-[#040b1f]/95 px-3 pb-3 pt-3 backdrop-blur-xl sm:px-5 lg:px-6">
      <div className="pywebview-drag-region flex min-w-0 flex-1 cursor-grab select-none items-center">
        <Logo />
      </div>
      <div className="flex shrink-0 items-center justify-end gap-2">
        <UpdateChecker />
        <div className="hidden items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary xl:flex">
          <ShieldCheck className="size-5" />
          <span>Interface local · Windows</span>
        </div>
        <WindowControls />
      </div>
    </header>
  )
}
