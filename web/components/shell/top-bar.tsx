"use client"

import { type PointerEvent as ReactPointerEvent } from "react"
import { desktopApi } from "@/lib/desktop"
import Link from "next/link"
import {usePathname} from "next/navigation"
import {useCloudUi} from "@/lib/cloud-ui"
import { ShieldCheck, Settings2, Cloud, Wifi, WifiOff } from "lucide-react"
import {T,useI18n} from "@/lib/i18n"
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
  const {t}=useI18n()
  const isCloud=usePathname().startsWith("/cloud")
  const {connected,setTab}=useCloudUi()
  const onHeaderPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (isCloud || !event.isPrimary || event.button !== 0) return
    const target = event.target
    // Native Windows caption drag must never intercept actionable controls.
    if (target instanceof Element &&
        target.closest('button,a,input,textarea,select,[role="button"],[data-no-window-drag]')) return
    const api = desktopApi()
    if (!api) return
    // Windows handles the entire drag, including cursor tracking, screen DPI,
    // multi-monitor movement and release. Do not capture pointer or call
    // Window.move in a WebView2 pointermove loop (broken in v51).
    event.preventDefault()
    void api.drag_window_native().catch(() => {})
  }

  return (
    <header
      onPointerDown={onHeaderPointerDown}
      className={"relative sticky top-0 z-[60] flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2 rounded-t-2xl border-b border-line/40 bg-[#040b1f]/95 px-2 py-2 select-none backdrop-blur-xl sm:gap-x-3 sm:px-5 sm:py-3 lg:px-6 "+(isCloud?"cursor-default":"cursor-grab active:cursor-grabbing")}
      aria-label={t("Barra superior — arraste para mover o DUELTRACE")}
    >
      {/* Authenticated native Win32 caption dragging handles the complete mouse gesture. */}
      <div className="pointer-events-none relative z-10 order-1 flex min-w-0 flex-1 select-none items-center">
        <Logo />
      </div>
      <div className="relative z-10 order-3 flex min-w-0 w-full items-center justify-start gap-2 sm:order-2 sm:w-auto sm:shrink-0 sm:justify-end">
        {isCloud ? <>
          <button type="button" onClick={()=>setTab("configuracoes")} data-no-window-drag
            aria-label={t("Configurações")} title={t("Configurações")}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/5 px-2 py-1.5 text-sm text-primary hover:bg-primary/15">
            <Settings2 className="size-4"/><span className="hidden sm:inline"><T k="Configurações"/></span>
          </button>
          <span className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-xs text-primary">
            {connected?<Wifi className="size-4"/>:<WifiOff className="size-4"/>}
            <span className="hidden min-[390px]:inline">{connected?"ePSXe Connector":"Conector desconectado"}</span>
            <Cloud className="size-4"/>
          </span>
        </> : <>
          <Link href="/configuracoes" data-no-window-drag aria-label={t("Configurações")} title={t("Configurações")}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/5 px-2 py-1.5 text-sm text-primary hover:bg-primary/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
            <Settings2 className="size-4"/><span className="hidden sm:inline"><T k="Configurações"/></span>
          </Link>
          <UpdateChecker />
        </>}
        {!isCloud&&<div className="hidden items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary 2xl:flex">
          <ShieldCheck className="size-5" />
          <span><T k="Interface local · Windows"/></span>
        </div>}
      </div>
      {!isCloud&&<div className="relative z-10 order-2 shrink-0 sm:order-3">
        <WindowControls />
      </div>}
    </header>
  )
}
