"use client"

import {useEffect,useRef,useState} from "react"
import {CheckCircle2,Clipboard,Download,FileKey2,KeyRound,LockKeyhole,ShieldCheck,XCircle} from "lucide-react"
import {desktopApi,type CommercialLicenseStatus} from "@/lib/desktop"

const LOCAL_PREVIEW:CommercialLicenseStatus={
  edition:"alpha",active:true,status:"not_required",
}

/** Local-first UX. The actual access check is ALWAYS on the Python API. */
export function CommercialActivationGuard({children}:{children:React.ReactNode}){
  const [license,setLicense]=useState<CommercialLicenseStatus|null>(null)
  const [connectionError,setConnectionError]=useState(false)
  const [request,setRequest]=useState<string|null>(null)
  const [error,setError]=useState("")
  const [info,setInfo]=useState("")
  const [busy,setBusy]=useState(false)
  const fileInput=useRef<HTMLInputElement>(null)
  const requestArea=useRef<HTMLTextAreaElement>(null)
  const primary=useRef<HTMLButtonElement>(null)

  useEffect(()=>{
    let alive=true
    let timer:number|undefined
    let attempts=0
    const probe=()=>{
      if(!alive)return
      const api=desktopApi()
      if(!api){
        if(window.location.hostname!=="127.0.0.1"){
          setLicense(LOCAL_PREVIEW)
          return
        }
        if(++attempts<40){timer=window.setTimeout(probe,450);return}
        setConnectionError(true)
        return
      }
      void api.commercial_license_status().then(result=>{
        if(alive){setLicense(result);setConnectionError(false)}
      }).catch(()=>{
        if(!alive)return
        if(++attempts<40){timer=window.setTimeout(probe,450)}
        else setConnectionError(true)
      })
    }
    timer=window.setTimeout(probe,300)
    window.addEventListener("pywebviewready",probe)
    return()=>{
      alive=false
      window.removeEventListener("pywebviewready",probe)
      if(timer!==undefined)window.clearTimeout(timer)
    }
  },[])

  const locked=license?.edition==="commercial-lite" && license.active!==true

  useEffect(()=>{
    if(!locked && !connectionError)return
    const oldOverflow=document.body.style.overflow
    document.body.style.overflow="hidden"
    primary.current?.focus()
    const keepDialogFocus=(e:KeyboardEvent)=>{
      if(e.key!=="Tab")return
      const dialog=document.getElementById("dueltrace-activation-dialog")
      if(!dialog)return
      const elements=Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not(:disabled),textarea:not(:disabled),input:not(:disabled)'))
        .filter(node=>node.offsetParent!==null)
      if(!elements.length)return
      const first=elements[0],last=elements[elements.length-1]
      if(e.shiftKey && document.activeElement===first){e.preventDefault();last.focus()}
      else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus()}
    }
    document.addEventListener("keydown",keepDialogFocus)
    return()=>{
      document.body.style.overflow=oldOverflow
      document.removeEventListener("keydown",keepDialogFocus)
    }
  },[locked,connectionError])

  const generateRequest=async()=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true);setError("");setInfo("")
    try{
      const result=await api.commercial_activation_request()
      setRequest(result.content)
      setInfo("Pedido gerado neste computador. Envie-o à Batoni Dev após a compra.")
    }catch(e){
      setError(e instanceof Error?e.message:"Não foi possível gerar o pedido.")
    }finally{setBusy(false)}
  }

  const copyRequest=async()=>{
    if(!request)return
    setError("")
    try{
      await navigator.clipboard.writeText(request)
      setInfo("Pedido copiado. Envie à Batoni Dev pelo canal de atendimento.")
    }catch{
      requestArea.current?.select()
      setInfo("Selecione e copie o texto do pedido para enviar à Batoni Dev.")
    }
  }

  const downloadRequest=()=>{
    if(!request)return
    const blob=new Blob([request+"\n"],{type:"application/json"})
    const url=URL.createObjectURL(blob)
    try{
      const link=document.createElement("a")
      link.href=url
      link.download="DUELTRACE-pedido-ativacao.json"
      document.body.appendChild(link)
      link.click()
      link.remove()
      setInfo("Se o arquivo foi salvo, envie-o à Batoni Dev para emitir sua licença.")
    }finally{window.setTimeout(()=>URL.revokeObjectURL(url),2000)}
  }

  const importFile=async(event:React.ChangeEvent<HTMLInputElement>)=>{
    const file=event.currentTarget.files?.[0]
    event.currentTarget.value=""
    if(!file)return
    if(file.size>8192 || !file.name.toLowerCase().endsWith(".json")){
      setError("Selecione um arquivo de licença JSON de até 8 KB.")
      return
    }
    const api=desktopApi()
    if(!api){setError("Conexão com o DUELTRACE indisponível.");return}
    setBusy(true);setError("");setInfo("")
    try{
      const raw=await file.text()
      const result=await api.commercial_activate_license(raw)
      if(!result.active)throw new Error("Licença não foi ativada.")
      setLicense(result)
      window.location.reload()
    }catch(e){
      setError(e instanceof Error?e.message:"Licença inválida. Verifique o arquivo.")
    }finally{setBusy(false)}
  }

  if(!locked && !connectionError)return <>{children}</>

  return <>
    <div aria-hidden="true" className="pointer-events-none select-none blur-sm">{children}</div>
    <div className="fixed inset-0 z-[9999] flex items-center justify-center overflow-y-auto bg-[#020712]/90 p-4 backdrop-blur-lg">
      <div id="dueltrace-activation-dialog" role="dialog" aria-modal="true"
        aria-labelledby="dueltrace-activation-title"
        className="my-auto max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-gold/45 bg-[#09192d] p-6 text-foreground shadow-[0_20px_85px_rgba(0,0,0,.8)]">
        <div className="mb-4 flex items-center gap-3">
          <span className="rounded-xl border border-gold/30 bg-gold/10 p-3 text-gold">
            <LockKeyhole className="size-6"/>
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.2em] text-gold/80">Batoni Dev</p>
            <h1 id="dueltrace-activation-title" className="font-display text-xl font-bold text-white">
              Ativar DUELTRACE
            </h1>
          </div>
        </div>
        <p className="text-sm leading-relaxed text-muted">
          A edição Commercial Lite utiliza uma licença de compra única, vinculada
          ao seu computador. A ativação funciona sem conexão permanente à internet.
        </p>
        {connectionError? <div role="alert" className="mt-5 rounded-lg border border-red-400/40 bg-red-500/10 p-4 text-sm">
          Não foi possível conectar à proteção local do DUELTRACE. Feche e abra o aplicativo novamente.
        </div>:<>
          <div className="mt-5 rounded-xl border border-primary/25 bg-[#061224] p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <KeyRound className="size-4"/> 1. Solicitar ativação
            </div>
            <p className="mb-3 text-xs text-muted">
              Gere o pedido neste PC e envie à Batoni Dev junto à identificação da compra.
            </p>
            <button ref={primary} type="button" disabled={busy} onClick={()=>void generateRequest()}
              className="btn-ghost rounded-lg border border-primary/40 px-3 py-2 text-xs font-semibold disabled:opacity-50">
              Gerar pedido de ativação
            </button>
            {request&&<>
              <textarea ref={requestArea} readOnly value={request}
                aria-label="Pedido de ativação"
                className="mt-3 h-24 w-full resize-none rounded-lg border border-line bg-[#030a15] p-2 font-mono text-xs text-foreground"/>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={()=>void copyRequest()}
                  className="btn-ghost inline-flex items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-xs">
                  <Clipboard className="size-4"/> Copiar pedido
                </button>
                <button type="button" onClick={downloadRequest}
                  className="btn-ghost inline-flex items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-xs">
                  <Download className="size-4"/> Salvar pedido
                </button>
              </div>
            </>}
          </div>
          <div className="mt-3 rounded-xl border border-gold/25 bg-[#061224] p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gold">
              <FileKey2 className="size-4"/> 2. Ativar licença recebida
            </div>
            <p className="mb-3 text-xs text-muted">
              Após receber seu arquivo de licença da Batoni Dev, selecione-o aqui.
            </p>
            <input ref={fileInput} type="file" accept=".json,application/json"
              className="sr-only" aria-label="Selecionar arquivo de licença"
              onChange={event=>void importFile(event)}/>
            <button type="button" disabled={busy} onClick={()=>fileInput.current?.click()}
              className="btn-gold inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold disabled:opacity-50">
              <ShieldCheck className="size-4"/> {busy?"Verificando…":"Selecionar licença (.json)"}
            </button>
          </div>
          {error&&<p role="alert" className="mt-3 flex items-start gap-2 text-xs text-red-300">
            <XCircle className="size-4 shrink-0"/>{error}
          </p>}
          {info&&<p role="status" className="mt-3 flex items-start gap-2 text-xs text-primary">
            <CheckCircle2 className="size-4 shrink-0"/>{info}
          </p>}
        </>}
        <p className="mt-5 border-t border-line/50 pt-3 text-xs text-muted">
          Nenhum endereço IP é usado para vincular a licença. Se trocar de PC,
          solicite a reemissão à Batoni Dev.
        </p>
        <button type="button" onClick={()=>void desktopApi()?.window_control("close")}
          className="mt-3 rounded-lg border border-line px-3 py-2 text-xs text-muted hover:text-white">
          Fechar DUELTRACE
        </button>
      </div>
    </div>
  </>
}
