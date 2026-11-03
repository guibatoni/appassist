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
  effectStatus?: string | null
  description?: string | null
  descriptionSource?: string | null
  level?: number | null
  attributeId?: number | null
  guardianStar1?: number | null
  guardianStar2?: number | null
  slot?: number
}

export type DeepScanResult = {
  sha256: string
  artCount: number
  thumbnailCount: number
  framedCards: number
  frameStyles: number
  opponentCount: number
  dropEntries: number
  descriptionCount: number
  effectTexts: number
  investigation: string
  status: string
}

export type LocalMod = {
  sha256: string
  name: string
  level: string
  cards: number
  fusions: number
  effects: number
  descriptions?: number
  framedCards?: number
  frameStyles?: number
  opponents?: number
  dropEntries?: number
  dropTables?: number
  rankDetected?: boolean
  rankBinaryVerified?: boolean
  rankOffset?: number | null
  rankMipsCandidates?: number
  rankMipsConfirmed?: boolean
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
  def: number | null
  type: string
  source: string
}

export type FusionPage = { total: number; offset: number; rows: FusionRow[] }

export type DropRow = {
  opponentId: number
  opponentName: string
  group: string
  cardId: number
  cardName: string
  cardType: string
  category: string
  atk: number | null
  def: number | null
  weight: number
  chancePercent: number
  sourceOffset: string | null
}

export type RankPoints = {
  available: boolean
  status: string
  source: string
  rules: Record<string, Array<{below: number; points: number}>>
  base_points: number | null
  lp_victory_bonus: number | null
  final_rank: boolean
  runtime_verified?: boolean
  binary_verified?: boolean
  structure_verified?: boolean
  method?: string | null
  first_offset?: number | null
  repeat_stride?: number | null
  layout_moved?: boolean
  criterion_names_verified?: boolean
  table_count?: number
  table_sha256?: string | null
  note: string
}

export type DropsPage = {
  available: boolean
  status: string
  total: number
  offset: number
  rows: DropRow[]
  opponents: Array<{id:number; name:string}>
  groups: string[]
  cardTypes: string[]
  rankLabelsVerified: boolean
  weightTotal: number
  source: string
  rankPoints: RankPoints | Record<string,never>
}

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
  latestPreview: string | null
  previewRunId: number | null
  previewVersion: string | null
  automaticInstallReady: boolean
  automaticInstallReason: string
  previewPage: string | null
  previewBranch: string | null
  previewBuildSha: string | null
  previewStatus?: "unavailable"
  previewError?: string | null
  releasePage: string
  status: "unavailable" | "update_available" | "up_to_date" | "preview" | "preview_ahead" | "preview_current" | "preview_update_available" | "preview_build_unknown" | "preview_older"
  updateAvailable: boolean
  message: string
}

export interface DesktopAPI {
  check_updates(): Promise<UpdateCheck>
  open_updates_page(runId?: number): Promise<{opened: boolean}>
  install_signed_update(): Promise<{started: boolean; status: string; version?: string}>
  get_state(): Promise<DesktopState>
  get_hand(): Promise<HandState>
  get_rank(): Promise<RankState>
  confirm_rank_lp(lifePoints: number): Promise<RankState>
  get_fusions(query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<FusionPage>
  get_drops(opponentId: number, group: string, query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<DropsPage>
  activate_mod(sha: string, acknowledge: boolean): Promise<DesktopState>
  scan_sources(sha: string): Promise<DeepScanResult>
  import_iso(): Promise<{cancelled: boolean; investigation?: string}>
  configure_epsxe(): Promise<{cancelled: boolean; configured?: boolean}>
  start_game(): Promise<{started: boolean; status: string}>
}

interface ProtectedNativeAPI {
  check_updates(token: string): Promise<UpdateCheck>
  open_updates_page(token: string, runId?: number): Promise<{opened: boolean}>
  install_signed_update(token: string): Promise<{started: boolean; status: string; version?: string}>
  get_state(token: string): Promise<DesktopState>
  get_hand(token: string): Promise<HandState>
  get_rank(token: string): Promise<RankState>
  confirm_rank_lp(token: string, lifePoints: number): Promise<RankState>
  get_fusions(token: string, query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<FusionPage>
  get_drops(token: string, opponentId: number, group: string, query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<DropsPage>
  activate_mod(token: string, sha: string, acknowledge: boolean): Promise<DesktopState>
  scan_sources(token: string, sha: string): Promise<DeepScanResult>
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
    open_updates_page: (runId) => native.open_updates_page(token, runId),
    install_signed_update: () => native.install_signed_update(token),
    get_state: () => native.get_state(token),
    get_hand: () => native.get_hand(token),
    get_rank: () => native.get_rank(token),
    confirm_rank_lp: (lifePoints) => native.confirm_rank_lp(token, lifePoints),
    get_fusions: (query, offset, limit, sort, cardType) => native.get_fusions(token, query, offset, limit, sort, cardType),
    get_drops: (opponentId, group, query, offset, limit, sort, cardType) => native.get_drops(token, opponentId, group, query, offset, limit, sort, cardType),
    activate_mod: (sha, acknowledge) => native.activate_mod(token, sha, acknowledge),
    scan_sources: (sha) => native.scan_sources(token, sha),
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

export function cardWithFrame(activeSha: string | null, id: number): string | null {
  if (!activeSha || !/^[a-f0-9]{64}$/.test(activeSha) ||
      !Number.isInteger(id) || id < 1 || id > 722) return null
  return `/__card__/${activeSha}/${id}.png`
}

export function cardArt(activeSha: string | null, id: number): string | null {
  if (!activeSha || !/^[a-f0-9]{64}$/.test(activeSha) ||
      !Number.isInteger(id) || id < 1 || id > 722) return null
  return `/__art__/${activeSha}/${id}.png`
}

export function sourceLabel(source: string): string {
  if (source === "observada_manualmente_no_jogo") return "Observada em duelo"
  if (source === "extraida_sete_bancos_consistentes") return "Receita validada no mod"
  if (source === "revisada_usuario_em_lote") return "Revisada pelo usuário"
  return "Origem não confirmada"
}
