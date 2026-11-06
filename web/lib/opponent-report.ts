import {desktopApi} from "./desktop"
import type {LocalMod, ModScanDiagnostic} from "./desktop"

/**
 * Copy only allowlisted, aggregated forensic counters.
 * Deliberately excludes filenames, ISO paths, SHA digests, card/opponent
 * names, raw bytes, serials, save data, and full layout diagnostics.
 */
const COUNTS = [
  "candidateReadable", "terminatedFF", "pointerCountDistinct",
  "pointerAliasCount", "pointerAliasGroups", "maxAliasMultiplicity",
  "pointerNonIncreasingPairs", "pointerSpanMin", "pointerSpanMax",
  "recordBoundaryKnown", "recordBoundaryReached", "recordWithHeader",
  "firstInvalidOffsetMin", "firstInvalidOffsetMax",
] as const
const CODES = new Set([
  "incompleto","ponteiros_repetidos","aliases_excessivos",
  "aliases_inconsistentes","ponteiros_fora_do_arquivo",
  "ponteiros_repetidos_ou_fora_de_ordem","ponteiro_intercalado",
  "marcador_alem_da_fronteira","marcadores_inconsistentes",
  "marcador_nao_suportado","dados_apos_marcador",
  "fronteira_fisica_fora_do_limite","marcador_nao_reproduzivel",
  "ultimo_registro_sem_limite_seguro","nomes_ou_codificacao_nao_conclusivos",
  "nomes_repetidos","delimitador_fisico_coerente",
])
const STATUS = new Set([
  "ff_encontrado", "glifo_invalido", "sem_ff_antes_proximo",
  "limite_leitura_sem_ff", "fim_arquivo_sem_ff",
])

function count(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) &&
    value >= -100000 && value <= 100000 ? value : null
}

function histogram(value: unknown, status: boolean): Record<string, number> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return {}
  const result: Record<string, number> = {}
  for (const [key, raw] of Object.entries(value).slice(0, 12)) {
    const allowed = status
      ? STATUS.has(key)
      : /^0x[0-9a-fA-F]{2}$/.test(key)
    const num = count(raw)
    if (allowed && num !== null && num >= 0 && num <= 39) result[key] = num
  }
  return result
}

export function safeOpponentReport(mod: LocalMod, diagnosis: ModScanDiagnostic): string {
  const evidence = diagnosis.opponentForensics
  if (!evidence || !Array.isArray(evidence.windows) || evidence.windows.length === 0) {
    throw new Error("Nenhuma evidência forense encontrada. Use Atualizar dados primeiro.")
  }
  const windows = evidence.windows.slice(0, 5).map(window => {
    const safe: Record<string, number | string | null | Record<string, number>> = {}
    for (const key of COUNTS) safe[key] = count(window?.[key])
    safe.boundaryDecision = typeof window?.boundaryDecision === "string" &&
      CODES.has(window.boundaryDecision) ? window.boundaryDecision : "incompleto"
    safe.statusHistogram = histogram(window?.statusHistogram, true)
    safe.firstInvalidByteHistogram = histogram(window?.firstInvalidByteHistogram, false)
    return safe
  })
  // Other extraction probes are already computed by the deterministic
  // scanner. Only counts and bounded status values leave the app.
  const searches: Record<string, {candidateCount: number | null; state: string}> = {}
  const allowedStates = new Set([
    "nao_encontrado", "tabela_candidata_localizada",
    "layout_candidato_localizado", "hipoteses_ambiguas",
    "referencias_mips_candidatas", "sem_evidencia", "indisponivel",
  ])
  for (const probe of ["namePointer", "relocatedNames", "mipsStaticReferences"] as const) {
    const source = diagnosis.opponentLayoutSearch?.probes?.[probe]
    searches[probe] = {
      candidateCount: count(source?.candidateCount),
      state: source?.state && allowedStates.has(source.state)
        ? source.state : "indisponivel",
    }
  }
  const report = {
    schema: 2,
    context: "dueltrace-opponent-pointers",
    scannerRevision: count(mod.scanParserRevision),
    cards: count(mod.cards),
    opponentCandidates: count(mod.opponentCandidateCount),
    opponentCount: count(mod.opponents),
    forensicWindows: windows,
    alternativeLayoutSearch: searches,
    disclaimer: "Dados candidatos. Nenhum ID, drop ou RANK foi validado em jogo.",
  }
  return JSON.stringify(report, null, 2)
}

export async function copyOpponentReport(mod: LocalMod): Promise<number> {
  const api = desktopApi()
  if (!api) throw new Error("Abra o DUELTRACE para Windows.")
  // Explicitly disable optional Ollama: this is a deterministic, read-only export.
  const diagnosis = await api.get_mod_scan_diagnostic(mod.sha256, false)
  const data = safeOpponentReport(mod, diagnosis)
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable")
    await navigator.clipboard.writeText(data)
  } catch {
    // Compatibility fallback for older WebView2. Never render private
    // diagnostic content as part of the page, even on clipboard failure.
    const field = document.createElement("textarea")
    field.value = data
    field.readOnly = true
    field.setAttribute("aria-hidden", "true")
    field.style.position = "fixed"
    field.style.left = "-10000px"
    document.body.appendChild(field)
    field.focus()
    field.select()
    let success = false
    try { success = document.execCommand("copy") }
    finally { field.remove() }
    if (!success) throw new Error(
      "Não foi possível copiar. Use o relatorio.json da pasta de análises.")
  }
  return diagnosis.opponentForensics?.windows.length ?? 0
}
