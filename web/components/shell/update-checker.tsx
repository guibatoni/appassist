"use client"

import { useEffect, useState } from "react"
import { ArrowUpRight, CheckCircle2, Download, RefreshCw, ShieldAlert, X } from "lucide-react"
import { desktopApi, type UpdateCheck } from "@/lib/desktop"

/**
 * Consulta automática após abertura; um clique inicia a instalação para
 * release estável assinada OU Preview oficial com SHA-256 e identidade do build.
 * Não altera as proteções do Windows nem executa artefatos Actions diretamente.
 */
export function UpdateChecker() {
  const [result, setResult] = useState<UpdateCheck | null>(null)
  const [visible, setVisible] = useState(false)
  const [checking, setChecking] = useState(false)
  const [opening, setOpening] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [automaticNotice, setAutomaticNotice] = useState(false)
  const [installFeedback, setInstallFeedback] = useState<string | null>(null)

  // Verificação automática UMA vez por inicialização, após a API local
  // pywebview disponibilizar o token. Não instala conteúdo em segundo plano.
  useEffect(() => {
    let mounted = true
    let attempts = 0
    let handle: number | undefined
    let recurring: number | undefined
    const refresh = () => {
      const api = desktopApi()
      if (!api) return
      void api.check_updates().then(response => {
        if (!mounted) return
        setResult(response)
        setAutomaticNotice(response.updateAvailable)
      }).catch(() => {
        // Falhas offline não geram notificações fictícias.
      })
    }
    const probe = () => {
      if (!mounted) return
      const api = desktopApi()
      if (!api) {
        if (++attempts <= 20) handle = window.setTimeout(probe, 750)
        return
      }
      refresh()
      // Consulta novamente se o usuário mantiver o DUELTRACE aberto.
      recurring = window.setInterval(refresh, 3 * 60 * 60 * 1000)
    }
    handle = window.setTimeout(probe, 1000)
    return () => {
      mounted = false
      if (handle !== undefined) window.clearTimeout(handle)
      if (recurring !== undefined) window.clearInterval(recurring)
    }
  }, [])

  const check = async () => {
    setVisible(true)
    setProblem(null)
    setInstallFeedback(null)
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

  const installOfficialUpdate = async () => {
    const api=desktopApi()
    if(!api || installing) return
    setInstallFeedback(null)
    setInstalling(true)
    try {
      // O próprio clique autoriza a instalação. Metadados são validados de novo.
      const fresh=await api.check_updates()
      setResult(fresh)
      setAutomaticNotice(fresh.updateAvailable)
      let outcome:{started:boolean;status:string;version?:string}|null=null
      if(fresh.automaticInstallReady) {
        outcome=await api.install_signed_update()
      } else if(fresh.automaticPortableReady) {
        outcome=await api.install_portable_update()
      } else if(fresh.automaticPreviewReady) {
        outcome=await api.install_preview_update()
      } else {
        setInstallFeedback(fresh.automaticInstallReason ||
          "Nenhum pacote de atualização aprovado está disponível.")
        return
      }
      setInstallFeedback(outcome.status)
      if(outcome.started)setAutomaticNotice(false)
    } catch(e) {
      setInstallFeedback(e instanceof Error ? e.message : "Não foi possível iniciar a atualização segura.")
    } finally {setInstalling(false)}
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
        className="size-2 animate-pulse rounded-full bg-gold"/>}
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
                {result.previewError && <p className="mt-2 text-xs text-gold" role="status">{result.previewError}</p>}
                <p className={"mt-3 flex items-start gap-2 text-sm " + (available ? "text-gold" : "text-foreground/85")}>
                  {available ? <Download className="size-5 shrink-0"/> : <CheckCircle2 className="size-5 shrink-0 text-primary"/>}
                  {result.message}
                </p>
                <button type="button" disabled={installing||checking}
                  onClick={()=>void installOfficialUpdate()}
                  className="btn-gold mt-3 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:opacity-50"
                  aria-label="Atualizar DUELTRACE automaticamente pelo GitHub">
                  <Download className="size-4"/>
                  {installing?"Baixando e verificando atualização…":"Atualizar agora"}
                </button>
                <p className="mt-2 text-xs text-muted">
                  O clique inicia a atualização na pasta atual, sem confirmação extra do aplicativo.
                  Pacotes são verificados por SHA-256 e identidade do build antes da substituição.
                  Instalação assinada continua opcional quando disponível.
                </p>
                {installFeedback&&<p className="mt-2 text-xs text-gold" role="status">
                  {installFeedback}
                </p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => void openOfficialPage(result.previewRunId ?? 0)}
                      disabled={opening} className="btn-gold inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:opacity-50">
                      {opening ? "Abrindo…" : (result.previewRunId != null ? "Abrir prévia no GitHub (manual)" : "Ver builds Preview")} <ArrowUpRight className="size-4"/>
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
          Atualizações Preview não assinadas têm risco maior que versões comerciais.
          Não desative o Defender nem ignore alertas do Windows. O botão usa
          pré-releases públicas do GitHub; builds legados permanecem em Actions.
        </p>
      </section>}
  </div>
}
