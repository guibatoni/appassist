import { ShieldCheck } from "lucide-react"
import { UpdateChecker } from "./update-checker"
import { WindowControls } from "./window-controls"

function Logo() {
  return (
    <div className="flex min-w-0 items-center gap-2 min-[390px]:gap-3">
      <svg viewBox="0 0 48 44" className="h-8 w-9 shrink-0 min-[390px]:h-9 min-[390px]:w-10 sm:h-11 sm:w-12" aria-hidden="true">
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
        <p className="bg-gradient-to-b from-white to-[#b9cbe6] bg-clip-text font-display text-xl font-extrabold italic tracking-wide text-transparent min-[390px]:text-2xl sm:text-3xl">
          DUELTRACE
        </p>
        <p className="mt-1 flex items-center gap-1 font-display text-[10px] italic text-gold min-[390px]:gap-2 sm:text-sm">
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
    <header className="sticky top-0 z-[60] flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2 rounded-t-2xl border-b border-line/40 bg-[#040b1f]/95 px-2 py-2 backdrop-blur-xl sm:gap-x-3 sm:px-5 sm:py-3 lg:px-6">
      <div className="pywebview-drag-region order-1 flex min-w-0 flex-1 cursor-grab select-none items-center">
        <Logo />
      </div>
      {/* On portrait/narrow windows, navigation and update controls must not
          crowd or push the native Close button outside the viewport. */}
      <div className="order-3 flex min-w-0 w-full items-center justify-start gap-2 sm:order-2 sm:w-auto sm:shrink-0 sm:justify-end">
        <UpdateChecker />
        <div className="hidden items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary 2xl:flex">
          <ShieldCheck className="size-5" />
          <span>Interface local · Windows</span>
        </div>
      </div>
      <div className="order-2 shrink-0 sm:order-3">
        <WindowControls />
      </div>
    </header>
  )
}
