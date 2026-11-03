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

export interface DesktopAPI {
  get_state(): Promise<DesktopState>
  get_hand(): Promise<HandState>
  get_fusions(query: string, offset: number, limit: number): Promise<FusionPage>
  activate_mod(sha: string, acknowledge: boolean): Promise<DesktopState>
  import_iso(): Promise<{cancelled: boolean; investigation?: string}>
  configure_epsxe(): Promise<{cancelled: boolean; configured?: boolean}>
  start_game(): Promise<{started: boolean; status: string}>
}

declare global {
  interface Window {
    pywebview?: { api?: DesktopAPI }
  }
}

export function desktopApi(): DesktopAPI | null {
  if (typeof window === "undefined") return null
  return window.pywebview?.api ?? null
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
