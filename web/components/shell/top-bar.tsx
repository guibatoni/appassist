"use client"

import { useRef, type PointerEvent as ReactPointerEvent } from "react"
import { desktopApi, type DesktopAPI } from "@/lib/desktop"
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

type ActiveDrag = {
  pointerId: number
  api: DesktopAPI
  dragId: number | null
  latestX: number
  latestY: number
  lastX: number
  lastY: number
  sending: boolean
  finished: boolean
  started: boolean
}

export function TopBar() {
  const currentDrag = useRef<ActiveDrag | null>(null)

  const endDrag = (state: ActiveDrag) => {
    if (state.finished) return
    state.finished = true
    if (currentDrag.current === state) currentDrag.current = null
    // Don't invalidate the native session while a final move is still
    // in-flight. endDrag is called after the move resolves instead.
    if (!state.sending && state.dragId !== null) {
      void state.api.drag_window_end(state.dragId).catch(() => {})
    }
  }

  const sendLatest = (state: ActiveDrag) => {
    if (state.finished || !state.started || state.sending || state.dragId === null) return
    const x = state.latestX
    const y = state.latestY
    if (x === state.lastX && y === state.lastY) return
    state.lastX = x
    state.lastY = y
    state.sending = true
    void state.api.drag_window_move(state.dragId, x, y)
      .then((response) => {
        if (!response.moved) endDrag(state)
      })
      .catch(() => endDrag(state))
      .finally(() => {
        state.sending = false
        if (state.finished) {
          if (state.dragId !== null) {
            void state.api.drag_window_end(state.dragId).catch(() => {})
          }
        } else {
          // Back-pressure: only one move request in flight; the latest
          // pointer location is kept even during a slow WebView2 bridge call.
          sendLatest(state)
        }
      })
  }

  const onHeaderPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (!event.isPrimary || event.button !== 0 || currentDrag.current) return
    const target = event.target
    // Update, window control, input and link interactions must NOT drag.
    if (target instanceof Element &&
        target.closest('button,a,input,textarea,select,[role="button"],[data-no-window-drag]')) return
    const api = desktopApi()
    if (!api) return
    const x = Math.round(event.screenX)
    const y = Math.round(event.screenY)
    const state: ActiveDrag = {
      pointerId: event.pointerId,
      api,
      dragId: null,
      latestX: x,
      latestY: y,
      lastX: x,
      lastY: y,
      sending: false,
      finished: false,
      started: false,
    }
    currentDrag.current = state
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      currentDrag.current = null
      return
    }
    event.preventDefault()
    void api.drag_window_begin(x, y)
      .then((result) => {
        if (!result.started || result.dragId === null) {
          endDrag(state)
          return
        }
        state.dragId = result.dragId
        state.started = true
        if (state.finished) {
          void api.drag_window_end(result.dragId).catch(() => {})
        } else {
          sendLatest(state)
        }
      })
      .catch(() => endDrag(state))
  }

  const onHeaderPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    const state = currentDrag.current
    if (!state || state.pointerId !== event.pointerId) return
    if ((event.buttons & 1) === 0) {
      endDrag(state)
      return
    }
    state.latestX = Math.round(event.screenX)
    state.latestY = Math.round(event.screenY)
    sendLatest(state)
  }

  const onHeaderPointerEnd = (event: ReactPointerEvent<HTMLElement>) => {
    const state = currentDrag.current
    if (state && state.pointerId === event.pointerId) endDrag(state)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  return (
    <header
      onPointerDown={onHeaderPointerDown}
      onPointerMove={onHeaderPointerMove}
      onPointerUp={onHeaderPointerEnd}
      onPointerCancel={onHeaderPointerEnd}
      onLostPointerCapture={onHeaderPointerEnd}
      className="relative sticky top-0 z-[60] flex min-w-0 flex-wrap items-center gap-x-2 gap-y-2 rounded-t-2xl border-b border-line/40 bg-[#040b1f]/95 px-2 py-2 cursor-grab select-none active:cursor-grabbing backdrop-blur-xl sm:gap-x-3 sm:px-5 sm:py-3 lg:px-6"
      aria-label="Barra superior — arraste para mover o DUELTRACE"
    >
      {/* Direct authenticated Window.move handles WebView2 mouse events,
          instead of pywebview-drag-region which failed on real Windows. */}
      <div className="pointer-events-none relative z-10 order-1 flex min-w-0 flex-1 select-none items-center">
        <Logo />
      </div>
      <div className="relative z-10 order-3 flex min-w-0 w-full items-center justify-start gap-2 sm:order-2 sm:w-auto sm:shrink-0 sm:justify-end">
        <UpdateChecker />
        <div className="hidden items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary 2xl:flex">
          <ShieldCheck className="size-5" />
          <span>Interface local · Windows</span>
        </div>
      </div>
      <div className="relative z-10 order-2 shrink-0 sm:order-3">
        <WindowControls />
      </div>
    </header>
  )
}
