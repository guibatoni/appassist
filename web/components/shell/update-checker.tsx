"use client"

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { BookOpen, CheckCircle2, Download, RefreshCw, ShieldAlert, X } from "lucide-react"
import { UpdatePatchNotes } from "./update-patch-notes"
import { desktopApi, type UpdateCheck } from "@/lib/desktop"

/**
 * Consulta automática e fluxo único: Atualizações > Baixar atualizações >
 * fechar, substituir arquivos na pasta atual e reabrir. Somente ZIP portátil
 * oficial verificado, sem criar outra pasta de instalação.
 */
export function UpdateChecker() {
  const [result, setResult] = useState<UpdateCheck | null>(null)
  const [visible, setVisible] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const [checking, setChecking] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [automaticNotice, setAutomaticNotice] = useState(false)
  const [installFeedback, setInstallFeedback] = useState<string | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!visible) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        setVisible(false)
      }
    }
    document.addEventListener("keydown", onKey)
    dialogRef.current?.focus()
    return () => {
      document.removeEventListener("keydown", onKey)
      triggerRef.current?.focus()
    }
  }, [visible])

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
      // Somente ZIP portátil in-place; instalador tradicional poderia escolher
      // outra pasta e não faz parte deste botão.
      if(fresh.automaticPortableReady) {
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
  const canDownload = available &&
    (result?.automaticPortableReady === true || result?.automaticPreviewReady === true)
  const statusText = available ?
    (canDownload ? "Nova versão disponível para download." :
      "Nova versão identificada; pacote ainda indisponível.") :
    result?.previewError ? result.previewError :
    result?.previewCheckStatus === "checked" ?
      "Consulta concluída: nenhuma Preview mais recente que o build instalado." :
    result?.status === "unavailable" ? "Não foi possível consultar novas versões." :
    "Nenhuma atualização nova disponível."
  const notesVersion = result?.patchNotesVersion ??
    (result?.currentVersion ?? "")
  const patchNotes = result?.patchNotes ?? []
  return <div className="relative">
    <button ref={triggerRef} type="button"
      className="btn-ghost inline-flex items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-xs font-semibold transition-colors hover:border-primary hover:text-white disabled:cursor-wait disabled:opacity-60"
      disabled={checking}
      onClick={() => void check()}
      aria-label="Abrir atualizações do DUELTRACE">
      <RefreshCw className={"size-4 text-primary" + (checking ? " animate-spin" : "")} />
      <span>{checking ? "Verificando…" : automaticNotice ? "Nova atualização" : "Atualizações"}</span>
      {automaticNotice && <span aria-label="Atualização identificada"
        className="size-2 animate-pulse rounded-full bg-gold"/>}
    </button>
    {/* The old absolutely-positioned popover was clipped by the main
        overflow-y-auto WebView panel. Render above that scroll container. */}
    {visible && typeof document !== "undefined" && createPortal(
      <div className="fixed inset-0 z-[9900] flex items-start justify-center overflow-y-auto bg-[#020713]/70 px-2 py-[max(1rem,env(safe-area-inset-top))] backdrop-blur-sm sm:items-center sm:px-4"
        onMouseDown={event=>{if(event.target===event.currentTarget)setVisible(false)}}>
        <section ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}
          className="dueltrace-scroll w-full max-w-[430px] max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-xl border border-gold/40 bg-[#0a1a31] p-3 text-sm text-foreground shadow-[0_12px_36px_rgba(0,0,0,.65)] outline-none sm:p-4"
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
            <p className="text-muted">Verificando atualizações…</p> :
            problem ?
              <p className="flex items-start gap-2 text-gold">
                <ShieldAlert className="size-4 shrink-0"/>{problem}
              </p> :
              result ? <>
                <p className="text-xs text-muted">
                  Instalada: <strong className="text-white">
                    v{result.currentVersion} {result.channel === "preview" ? "Preview" : "Estável"}
                    {result.installedPreviewRunId ? ` · build #${result.installedPreviewRunId}` : ""}
                  </strong>
                </p>
                {available&&<p className="mt-1 text-xs text-muted">
                  Disponível: <strong className="text-white">
                    {result.automaticPortableReady ? result.latestStable :
                      result.previewVersion ? `v${result.previewVersion} Preview · build #${result.previewRunId ?? "?"}` :
                        result.latestStable ?? "Nova versão"}
                  </strong>
                </p>}
                <p className={"mt-3 flex items-start gap-2 " +
                  (available ? "text-gold" : "text-foreground/85")}>
                  {available ? <Download className="size-5 shrink-0"/> :
                    <CheckCircle2 className="size-5 shrink-0 text-primary"/>}
                  {statusText}
                </p>
              </> :
              <p className="text-muted">Nenhuma consulta realizada.</p>}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button type="button" disabled={!canDownload||installing||checking}
            onClick={()=>void installOfficialUpdate()}
            className="btn-gold inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Atualizar agora">
            <Download className="size-4"/>
            {installing?"Baixando atualização…":"Atualizar agora"}
          </button>
          <button type="button" disabled={checking}
            onClick={()=>setNotesOpen(true)}
            className="btn-ghost inline-flex items-center gap-2 rounded-lg border border-primary/40 px-3 py-2 text-xs transition-colors hover:border-primary disabled:opacity-50"
            aria-label="Abrir patch notes">
            <BookOpen className="size-4 text-primary"/>Patch notes
          </button>
        </div>
        {installFeedback&&<p className="mt-3 text-xs text-gold" role="status">
          {installFeedback}
        </p>}
        </section>
      </div>, document.body)}
    <UpdatePatchNotes open={notesOpen} onClose={()=>setNotesOpen(false)}
      version={notesVersion} notes={patchNotes}/>
  </div>
}
