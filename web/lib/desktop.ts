"use client"

import { useCallback, useEffect, useState } from "react"

export type LocalCard = {
  id: number
  name: string
  type: string
  category: string
  attribute: string
  atk: number | null
  def: number | null
  effect: string | null
  effectSource: string | null
  description?: string | null
  descriptionSource?: string | null
  slot?: number
}

export type LocalMod = {
  sha256: string
  name: string
  level: string
  cards: number
  fusions: number
  effects: number
  requiresReview: boolean
}

export type DesktopState = {
  connected: boolean
  source: string
  activeSha: string | null
  activeName: string | null
  cards: LocalCard[]
  mods: LocalMod[]
  fusionCount: number
  epsxeConfigured: boolean
  warning: string
  framePalettes?: Record<string,{accent:string;source:string;wa_offset:number}>
  descriptionAudit?: {status?:string;recognized?:number}
}

export type DirectFusion = {
  slot_a: number
  slot_b: number
  a: number
  b: number
  result: number
  result_name: string
  atk: number | null
  validation: string
}

export type Chain = {
  result: number
  result_name: string
  atk: number | null
  slot_order: number[]
  steps: Array<{
    material_a: number
    material_b: number
    result: number
    validation: string
  }>
}

export type HandState = {
  ready: boolean
  status: string
  hand: LocalCard[]
  pairs: DirectFusion[]
  chains: Chain[]
  chainsComplete?: boolean
}

export type FusionRow = {
  a: number
  b: number
  result: number
  nameA: string
  nameB: string
  nameResult: string
  atk: number | null
  source: string
}

export type FusionPage = { total: number; offset: number; rows: FusionRow[] }

export type RankState = {
  ready: boolean
  state: "unsupported" | "unavailable" | "needs_lp_confirmation" | "lp_mismatch" | "provisional"
  status: string
  candidateLp?: number
  score: number | null
  category: string | null
  counters: Record<string, number> | null
  breakdown?: Record<string, number>
  model?: string
  final?: boolean
}

export type UpdateCheck = {
  currentVersion: string
  channel: "stable" | "preview"
  latestStable: string | null
  releasePage: string
  status: "unavailable" | "update_available" | "up_to_date" | "preview" | "preview_ahead"
  updateAvailable: boolean
  message: string
}

export interface DesktopAPI {
  check_updates(): Promise<UpdateCheck>
  open_updates_page(): Promise<{opened: boolean}>
  get_state(): Promise<DesktopState>
  get_hand(): Promise<HandState>
  get_rank(): Promise<RankState>
  confirm_rank_lp(lifePoints: number): Promise<RankState>
  get_fusions(query: string, offset: number, limit: number): Promise<FusionPage>
  activate_mod(sha: string, acknowledge: boolean): Promise<DesktopState>
  import_iso(): Promise<{cancelled: boolean; investigation?: string}>
  configure_epsxe(): Promise<{cancelled: boolean; configured?: boolean}>
  start_game(): Promise<{started: boolean; status: string}>
}

interface ProtectedNativeAPI {
  check_updates(token: string): Promise<UpdateCheck>
  open_updates_page(token: string): Promise<{opened: boolean}>
  get_state(token: string): Promise<DesktopState>
  get_hand(token: string): Promise<HandState>
  get_rank(token: string): Promise<RankState>
  confirm_rank_lp(token: string, lifePoints: number): Promise<RankState>
  get_fusions(token: string, query: string, offset: number, limit: number): Promise<FusionPage>
  activate_mod(token: string, sha: string, acknowledge: boolean): Promise<DesktopState>
  import_iso(token: string): Promise<{cancelled: boolean; investigation?: string}>
  configure_epsxe(token: string): Promise<{cancelled: boolean; configured?: boolean}>
  start_game(token: string): Promise<{started: boolean; status: string}>
}

declare global {
  interface Window {
    pywebview?: { api?: ProtectedNativeAPI }
    __DUELTRACE_TOKEN__?: string
  }
}

export function desktopApi(): DesktopAPI | null {
  if (typeof window === "undefined" || window.top !== window) return null
  if (window.location.protocol !== "http:" ||
      window.location.hostname !== "127.0.0.1") return null
  const native = window.pywebview?.api
  const token = window.__DUELTRACE_TOKEN__
  if (!native || typeof token !== "string" || token.length < 32) return null
  return {
    check_updates: () => native.check_updates(token),
    open_updates_page: () => native.open_updates_page(token),
    get_state: () => native.get_state(token),
    get_hand: () => native.get_hand(token),
    get_rank: () => native.get_rank(token),
    confirm_rank_lp: (lifePoints) => native.confirm_rank_lp(token, lifePoints),
    get_fusions: (query, offset, limit) => native.get_fusions(token, query, offset, limit),
    activate_mod: (sha, acknowledge) => native.activate_mod(token, sha, acknowledge),
    import_iso: () => native.import_iso(token),
    configure_epsxe: () => native.configure_epsxe(token),
    start_game: () => native.start_game(token),
  }
}

export function useDesktopState() {
  const [state, setState] = useState<DesktopState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const api = desktopApi()
    if (!api) {
      setState(null)
      setError("Esta é apenas a prévia visual. Abra a versão Windows para ler seus mods reais.")
      setLoading(false)
      return
    }
    try {
      setState(await api.get_state())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao consultar o motor local.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    // O WebView injeta a API após o primeiro carregamento.
    window.addEventListener("pywebviewready", refresh)
    const id = window.setInterval(() => {
      if (!desktopApi()) return
      if (!state) void refresh()
    }, 1500)
    return () => {
      window.removeEventListener("pywebviewready", refresh)
      window.clearInterval(id)
    }
  }, [refresh, state])

  return {state, error, loading, refresh}
}

export function cardArt(activeSha: string | null, id: number): string | null {
  if (!activeSha || !/^[a-f0-9]{64}$/.test(activeSha) ||
      !Number.isInteger(id) || id < 1 || id > 722) return null
  return `/__art__/${activeSha}/${id}.png`
}

export function sourceLabel(source: string): string {
  if (source === "observada_manualmente_no_jogo") return "Observada em duelo"
  if (source === "extraida_sete_bancos_consistentes") return "Extraída da ISO ×7"
  if (source === "revisada_usuario_em_lote") return "Revisada pelo usuário"
  return "Origem não confirmada"
}
