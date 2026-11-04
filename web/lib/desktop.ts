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

export type LayoutFileCandidate = {
  name: string
  size: number | null
  score: number
  signals: string[]
  dropArrayMatches: number
  psxHeader: boolean
  validated: false
}

export type ModScanDiagnostic = {
  romSha?: string
  state: string
  status: string
  issues: string[]
  nextSteps: string[]
  executableCandidates: string[]
  waCandidates: string[]
  layoutCandidates?: {
    schema: number | null
    inspectedFiles: number
    resourceProbes: number
    executables: LayoutFileCandidate[]
    resources: LayoutFileCandidate[]
    note: string
    verified: false
  }
  waSelectionMethod?: string
  waSizeCandidates?: string[]
  suspectedWa?: string | null
  suspectedWaVerified?: boolean
  chosenExecutable: string
  chosenWa: string
  exeSize: number | null
  waSize: number | null
  sectorBytes: number | null
  indexedFiles: number
  files: Array<{name: string; size: number | null; lba: number | null; signature?: string}>
  possibleResourceFiles?: Array<{name: string; size: number}>
  systemCnf: {
    found: boolean
    bootTarget: string | null
    bootTargetIndexed: boolean | null
    bootFileSignature?: string | null
    status: string
  }
  hashExe: string | null
  hashWa: string | null
  cardsVerified: boolean
  dropsVerified: boolean
  artVerified: boolean
  opponentNameBoundaries?: {
    state: string
    examined: number
    hasFFBeforeNext: number
    noFFBeforeNext: number
    commonEndByte: string | null
    commonEndByteCount: number
    commonFirstInvalidByte: string | null
    commonFirstInvalidCount: number
    validated: false
    samples: Array<{
      id: number | null
      pointer: number | null
      nextPointerDelta: number | null
      headerPresent: boolean
      hasFFBeforeNext: boolean | null
      firstInvalidHex: string | null
      firstInvalidOffset: number | null
      endByteHex: string | null
      tailHex: string
      readablePrefix: string
    }>
  }
  opponentPointerProbe?: {
    state: string
    verified: false
    candidates: Array<{
      startIndex: number
      plausible: number
      distinct: number
      samples: string[]
      validated: false
    }>
  }
  nameLayoutProbe?: {
    state: string
    cardSamples: Array<{index: number|null; pointer: number|null; name: string; status: string; invalidGlyphs: number|null}>
    opponentSamples: Array<{index: number|null; pointer: number|null; name: string; status: string; invalidGlyphs: number|null}>
    cardPlausibleSamples: number
    opponentPlausibleSamples: number
    note: string
  }
  automaticExtractionComplete: boolean
  aiRole: string
  ai?: {
    state: string
    message?: string
    resumo?: string
    summarySuppressed?: boolean
    note?: string
    prioridades?: string[]
    alertas?: string[]
  }
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
  diagnostic?: ModScanDiagnostic
  aiState?: string
  aiMessage?: string
  status: string
}

export type CardMatchRow = {
  sourceId: number
  sourceName: string
  targetId: number | null
  targetName: string | null
  confidence: "alta" | "revisar" | "sem_correspondencia"
  signals: string[]
  sameId: boolean | null
  ambiguous: boolean
  candidateCount: number
  score: number | null
}

export type CardAIMatchReport = {
  status: string
  model?: string
  analysed: number
  revisoes: Array<{
    sourceId: number
    targetId: number
    assessment: "manter_candidata" | "revisar" | "descartar"
    reason: string
  }>
  verifiedInGame: false
  updatedProfiles?: false
  note: string
}

export type CardMatchResult = {
  sourceSha: string
  targetSha: string
  sourceName: string
  targetName: string
  sourceCards: number
  targetCards: number
  summary: {
    alta: number
    revisar: number
    sem_correspondencia: number
    reordered: number
    sourceArtCount: number
    targetArtCount: number
  }
  rows: CardMatchRow[]
  total: number
  offset: number
  status: string
  verifiedInGame: boolean
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
  dropCandidateEntries?: number
  dropCandidateTables?: number
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
  groupLabel: string
  eligibleRanks: string[]
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

export type RankAuditExport = {
  cancelled: boolean
  file?: string
  reportSha256?: string
  bytes?: number
  status?: string
}

export type MipsTraceResult = {
  cancelled?: boolean
  available?: boolean
  status: string
  records?: number
  correlatedDuels?: number
  tableReadReports?: number
  rankTableEvidence?: {
    status:string
    tableReadsObserved:boolean
    matchedPairs:number
    memoryEvents:number
    candidateWindows:Array<{candidatePC:string;matchedPairs:number;memoryBaseCandidate:string}>
    rankRoutineConfirmed:boolean
  }
  duel_id?: string | null
  record_id?: string
  executionEvidence?: boolean
  rankRoutineConfirmed?: boolean
  executedCandidates?: Array<{pc:string;hits:number}>
  instructionSamples?: number
  distinctPCs?: number
  note?: string
  last?: MipsTraceResult | null
}

export type DuelEvidence = {
  status: string
  observations: number
  lastDuelId: string | null
  usable: number
  ambiguous: number
  inconsistent: number
  rankMappings: Record<string,{group:string;status:string}>
  assignmentCount?: number
  mappingConsistency?: string
  possibleGroups?: Record<string,string[]>
  suspectedMappings: Record<string,{group:string;groupDisplay?:string;observations:number;opponents:number;status:string}>
  mismatches: Array<{duelId?:string;rank?:string;opponentId?:number;cardId?:number;reason:string}>
  scoreComparisons: {compared:number;exact:number;different:number;status:string}
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
  groupOptions: Array<{value:string;label:string;ranks:string[]}>
  rankOptions: string[]
  rankSelected: string
  rankSystem: "x15" | "classic" | null
  cardTypes: string[]
  rankLabelsVerified: boolean
  weightTotal: number
  source: string
  rankPoints: RankPoints | Record<string,never>
}

export type RankDiagnostic = {
  readyForLiveRead: boolean
  code: string
  reason: string
  nextStep: string
  isoShaPrefix: string | null
  rankSystem: "classic" | "x15" | null
  rankTableDetected: boolean
  rankStructureVerified: boolean
  mipsCandidates: number
  ramBindingPresent: boolean
  ramBindingVerified: boolean
  x15Exact: boolean
  x15CompatibleBinary: boolean
  mipsRuntimeConfirmed: boolean
  legacyProbeAvailable?: boolean
  score: null
  projectedRank: null
  note: string
}

export type SpoilsCounters = {
  turns: number
  effective_attacks: number
  defense_wins: number
  face_down: number
  spells: number
  traps: number
  cards_used: number
  remaining_lp: number
  fusions: number
  equips: number
}
export type SpoilsResult = {
  score: number
  category: string
  rankSystem: "classic" | "x15"
  basePoints: number
  victoryBonus: number
  victory: "lp" | "deckout" | "exodia"
  breakdown: Record<keyof SpoilsCounters,number>
  source: string
  verifiedInEmulator: false
  note: string
}

export type RankState = {
  ready: boolean
  state: "unsupported" | "unavailable" | "needs_lp_confirmation" | "needs_ram_validation" | "lp_mismatch" | "provisional"
  status: string
  diagnosticCode?: string
  sourceMode?: "verified" | "experimental"
  validationProgress?: number
  validationRequired?: number
  candidateLp?: number
  score: number | null
  category: string | null
  rankSystem?: "x15" | "classic"
  counters: Record<string, number> | null
  breakdown?: Record<string, number>
  model?: string
  victorySource?: "projected_lp" | "ram_lp" | "ram_deckout"
  victoryBonus?: number
  final?: boolean
}

export type RankCapture = {
  ready: boolean
  captureId: string | null
  score: number | null
  category: string | null
  status: string
}

export type RankComparison = {
  available: boolean
  status: string
  total?: number
  fully_comparable?: number
  matches?: number
  mismatches?: number
  rank_only_matches?: number
  rank_only_mismatches?: number
  invalid?: number
  missing_prediction?: number
  not_lp_win?: number
  runtime_verified?: boolean
  cases: Array<{
    duel_id: string | null
    status: string
    observed_rank: string | null
    observed_points: number | null
    projected_rank: string | null
    projected_score: number | null
    score_delta: number | null
  }>
}

export type UpdateCheck = {
  currentVersion: string
  channel: "stable" | "preview"
  latestStable: string | null
  latestPreview: string | null
  previewRunId: number | null
  previewVersion: string | null
  automaticInstallReady: boolean
  automaticPreviewReady?: boolean
  automaticPortableReady?: boolean
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
  install_preview_update(): Promise<{started: boolean; status: string; version?: string}>
  install_portable_update(): Promise<{started: boolean; status: string; version?: string}>
  compare_mod_cards(sourceSha: string, targetSha: string, query?: string, offset?: number, limit?: number, confidence?: string): Promise<CardMatchResult>
  review_card_matches(sourceSha: string, targetSha: string): Promise<CardAIMatchReport>
  get_state(): Promise<DesktopState>
  get_hand(): Promise<HandState>
  get_rank(): Promise<RankState>
  calculate_spoils(counters: SpoilsCounters, victory: "lp"|"deckout"|"exodia"): Promise<SpoilsResult>
  get_rank_diagnostic(): Promise<RankDiagnostic>
  confirm_rank_lp(lifePoints: number): Promise<RankState>
  capture_rank_prediction(): Promise<RankCapture>
  get_pending_rank_capture(): Promise<RankCapture>
  get_rank_comparison(): Promise<RankComparison>
  get_fusions(query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<FusionPage>
  get_drops(opponentId: number, group: string, query: string, offset: number, limit: number, sort?: string, cardType?: string, rank?: string): Promise<DropsPage>
  get_rank_trace_status(): Promise<MipsTraceResult>
  import_rank_trace(duelId?: string | null): Promise<MipsTraceResult>
  export_rank_audit(): Promise<RankAuditExport>
  get_duel_evidence(): Promise<DuelEvidence>
  record_duel_result(opponentId: number, observedRank: string, cardId: number, observedPoints?: number | null, victoryType?: string, captureId?: string | null): Promise<DuelEvidence>
  activate_mod(sha: string, acknowledge: boolean): Promise<DesktopState>
  scan_sources(sha: string): Promise<DeepScanResult>
  get_mod_scan_diagnostic(sha: string, withOllama?: boolean): Promise<ModScanDiagnostic>
  import_iso(): Promise<{cancelled: boolean; investigation?: string}>
  configure_epsxe(): Promise<{cancelled: boolean; configured?: boolean}>
  start_game(): Promise<{started: boolean; status: string}>
}

interface ProtectedNativeAPI {
  check_updates(token: string): Promise<UpdateCheck>
  open_updates_page(token: string, runId?: number): Promise<{opened: boolean}>
  install_signed_update(token: string): Promise<{started: boolean; status: string; version?: string}>
  install_preview_update(token: string): Promise<{started: boolean; status: string; version?: string}>
  install_portable_update(token: string): Promise<{started: boolean; status: string; version?: string}>
  compare_mod_cards(token: string, sourceSha: string, targetSha: string, query?: string, offset?: number, limit?: number, confidence?: string): Promise<CardMatchResult>
  review_card_matches(token: string, sourceSha: string, targetSha: string): Promise<CardAIMatchReport>
  get_state(token: string): Promise<DesktopState>
  get_hand(token: string): Promise<HandState>
  get_rank(token: string): Promise<RankState>
  calculate_spoils(token: string, counters: SpoilsCounters, victory: "lp"|"deckout"|"exodia"): Promise<SpoilsResult>
  get_rank_diagnostic(token: string): Promise<RankDiagnostic>
  confirm_rank_lp(token: string, lifePoints: number): Promise<RankState>
  capture_rank_prediction(token: string): Promise<RankCapture>
  get_pending_rank_capture(token: string): Promise<RankCapture>
  get_rank_comparison(token: string): Promise<RankComparison>
  get_fusions(token: string, query: string, offset: number, limit: number, sort?: string, cardType?: string): Promise<FusionPage>
  get_drops(token: string, opponentId: number, group: string, query: string, offset: number, limit: number, sort?: string, cardType?: string, rank?: string): Promise<DropsPage>
  get_rank_trace_status(token: string): Promise<MipsTraceResult>
  import_rank_trace(token: string, duelId?: string | null): Promise<MipsTraceResult>
  export_rank_audit(token: string): Promise<RankAuditExport>
  get_duel_evidence(token: string): Promise<DuelEvidence>
  record_duel_result(token: string, opponentId: number, observedRank: string, cardId: number, observedPoints?: number | null, victoryType?: string, captureId?: string | null): Promise<DuelEvidence>
  activate_mod(token: string, sha: string, acknowledge: boolean): Promise<DesktopState>
  scan_sources(token: string, sha: string): Promise<DeepScanResult>
  get_mod_scan_diagnostic(token: string, sha: string, withOllama?: boolean): Promise<ModScanDiagnostic>
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
    install_preview_update: () => native.install_preview_update(token),
    install_portable_update: () => native.install_portable_update(token),
    review_card_matches: (sourceSha,targetSha) => native.review_card_matches(token,sourceSha,targetSha),
    compare_mod_cards: (sourceSha,targetSha,query,offset,limit,confidence) =>
      native.compare_mod_cards(token,sourceSha,targetSha,query,offset,limit,confidence),
    get_state: () => native.get_state(token),
    get_hand: () => native.get_hand(token),
    get_rank: () => native.get_rank(token),
    calculate_spoils: (counters,victory) => native.calculate_spoils(token,counters,victory),
    get_rank_diagnostic: () => native.get_rank_diagnostic(token),
    confirm_rank_lp: (lifePoints) => native.confirm_rank_lp(token, lifePoints),
    capture_rank_prediction: () => native.capture_rank_prediction(token),
    get_pending_rank_capture: () => native.get_pending_rank_capture(token),
    get_rank_comparison: () => native.get_rank_comparison(token),
    get_fusions: (query, offset, limit, sort, cardType) => native.get_fusions(token, query, offset, limit, sort, cardType),
    get_drops: (opponentId, group, query, offset, limit, sort, cardType, rank) => native.get_drops(token, opponentId, group, query, offset, limit, sort, cardType, rank),
    get_rank_trace_status: () => native.get_rank_trace_status(token),
    import_rank_trace: (duelId) => native.import_rank_trace(token, duelId),
    export_rank_audit: () => native.export_rank_audit(token),
    get_duel_evidence: () => native.get_duel_evidence(token),
    record_duel_result: (opponentId, observedRank, cardId, observedPoints, victoryType, captureId) =>
      native.record_duel_result(token, opponentId, observedRank, cardId, observedPoints, victoryType, captureId),
    activate_mod: (sha, acknowledge) => native.activate_mod(token, sha, acknowledge),
    scan_sources: (sha) => native.scan_sources(token, sha),
    get_mod_scan_diagnostic: (sha,withOllama) => native.get_mod_scan_diagnostic(token,sha,withOllama),
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
