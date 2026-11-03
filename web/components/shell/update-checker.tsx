"use client"

import { useEffect, useState } from "react"
import { ArrowUpRight, CheckCircle2, Download, RefreshCw, ShieldAlert, X } from "lucide-react"
import { desktopApi, type UpdateCheck } from "@/lib/desktop"

/**
 * Consulta automática após abertura e opção de verificação manual. Não instala binários.
 * A abertura da página oficial é feita no navegador do Windows pelo motor Python.
 */
export function UpdateChecker() {
  const [result, setResult] = useState<UpdateCheck | null>(null)
  const [visible, setVisible] = useState(false)
  const [checking, setChecking] = useState(false)
  const [opening, setOpening] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [automaticNotice, setAutomaticNotice] = useState(false)

  // Verificação automática UMA vez por inicialização, após a API local
  // pywebview disponibilizar o token. Não instala conteúdo em segundo plano.
  useEffect(() => {
    let mounted = true
    let attempts = 0
    let handle: ReturnType<typeof setTimeout> | undefined
    const probe = () => {
      if (!mounted) return
      const api = desktopApi()
      if (!api) {
        if (++attempts <= 20) handle = window.setTimeout(probe, 750)
        return
      }
      void api.check_updates().then(response => {
        if (!mounted) return
        setResult(response)
        setAutomaticNotice(response.updateAvailable)
      }).catch(() => {
        // Falhas offline não geram alertas falsos. O botão permite retentar.
      })
    }
    handle = window.setTimeout(probe, 1000)
    return () => {
      mounted = false
      if (handle !== undefined) window.clearTimeout(handle)
    }
  }, [])

  const check = async () => {
    setVisible(true)
    setProblem(null)
    const api = desktopApi()
    if (!api) {
      setResult(null)
      setProblem("Abra o aplicativo DUELTRACE para Windows para consultar novas versões.")
      return
    }
    setChecking(true)
    try {
      const response = await api.check_updates()
      setResult(response)
      setAutomaticNotice(response.updateAvailable)
    } catch {
      setResult(null)
      setProblem("Não foi possível consultar as versões. Verifique a conexão e tente novamente.")
    } finally {
      setChecking(false)
    }
  }

  const openOfficialPage = async (runId?: number) => {
    const api = desktopApi()
    if (!api) return
    setOpening(true)
    try {
      await api.open_updates_page(runId)
      setProblem(null)
    } catch {
      setProblem("Não foi possível abrir o navegador padrão. Acesse github.com/guibatoni/appassist/actions ou /releases.")
    } finally {
      setOpening(false)
    }
  }

  const available = result?.updateAvailable === true
  return <div className="relative">
    <button type="button"
      className="btn-ghost inline-flex items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-xs font-semibold transition-colors hover:border-primary hover:text-white disabled:cursor-wait disabled:opacity-60"
      disabled={checking}
      onClick={() => void check()}
      aria-label="Verificar atualizações do DUELTRACE">
      <RefreshCw className={"size-4 text-primary" + (checking ? " animate-spin" : "")} />
      <span>{checking ? "Verificando…" : automaticNotice ? "Nova versão disponível" : "Verificar atualizações"}</span>
      {automaticNotice && <span aria-label="Atualização identificada"
        className="size-2 animate-pulse rounded-full bg-gold"/>
    </button>
    {visible &&
      <section className="absolute right-0 top-full z-50 mt-2 w-[min(90vw,370px)] rounded-xl border border-gold/40 bg-[#0a1a31] p-4 text-sm text-foreground shadow-[0_12px_36px_rgba(0,0,0,.65)]"
        aria-label="Resultado da verificação">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-base font-semibold text-gold">Atualizações DUELTRACE</h3>
          <button type="button" aria-label="Fechar resultado" onClick={() => setVisible(false)}
            className="rounded-md p-1 text-muted transition-colors hover:bg-primary/10 hover:text-white">
            <X className="size-4" />
          </button>
        </div>
        <div aria-live="polite" className="mt-3">
          {checking ?
            <p className="text-muted">Consultando lançamentos oficiais no GitHub…</p> :
            problem ?
              <p className="flex items-start gap-2 text-gold"><ShieldAlert className="size-4 shrink-0"/>{problem}</p> :
              result ? <>
                <div className="flex items-center gap-2 text-xs text-muted">
                  <span>Instalada: <strong className="text-white">v{result.currentVersion} {result.channel === "preview" ? "Preview" : "Estável"}</strong></span>
                </div>
                <p className="mt-1 text-xs text-muted">Última estável: <strong className="text-white">{result.latestStable ?? "Indisponível"}</strong></p>
                <p className="mt-1 text-xs text-muted">Preview encontrada: <strong className="text-white">{result.previewVersion ? "v"+result.previewVersion : "Indisponível"}</strong></p>
                <p className="mt-1 text-xs text-muted">Preview Windows: <strong className="text-white">{result.previewRunId ? `Build #${result.previewRunId} · ${result.previewBuildSha ?? "SHA indisponível"}` : "Não identificado"}</strong></p>
                <p className={"mt-3 flex items-start gap-2 text-sm " + (available ? "text-gold" : "text-foreground/85")}>
                  {available ? <Download className="size-5 shrink-0"/> : <CheckCircle2 className="size-5 shrink-0 text-primary"/>}
                  {result.message}
                </p>
                {!result.automaticInstallReady && <p className="mt-3 text-xs text-gold">
                  Instalação automática indisponível até termos instalador assinado digitalmente.
                </p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => void openOfficialPage(result.previewRunId ?? 0)}
                      disabled={opening} className="btn-gold inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:opacity-50">
                      {opening ? "Abrindo…" : (result.previewRunId != null ? "Abrir pacote Preview" : "Ver builds Preview")} <ArrowUpRight className="size-4"/>
                    </button>
                  <button type="button" onClick={() => void openOfficialPage()}
                    disabled={opening} className="btn-ghost inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:opacity-50">
                    Ver versões estáveis <ArrowUpRight className="size-4"/>
                  </button>
                </div>
              </> :
              <p className="text-muted">Nenhuma consulta realizada.</p>}
        </div>
        <p className="mt-3 border-t border-line/50 pt-2 text-xs text-muted">
          Prévia experimental NÃO ASSINADA. Um antivírus sem detecções não garante
          segurança. Não ignore bloqueios do Chrome/Windows. Builds de teste
          ficam no GitHub Actions → Artifacts e podem exigir login.
        </p>
      </section>}
  </div>
}
