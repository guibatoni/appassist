"use client"

import {useEffect,useState} from "react"
import {Copy,Minus,Square,X} from "lucide-react"
import {desktopApi} from "@/lib/desktop"

type WindowAction="minimize"|"toggle_maximize"|"close"

export function WindowControls() {
  const [connected,setConnected]=useState(false)
  const [maximized,setMaximized]=useState(false)
  const [busy,setBusy]=useState<WindowAction|null>(null)

  // A capacidade nativa é entregue depois da página iniciar. Não inventar
  // controles funcionais no browser nem expor a janela pelo HTTP local.
  useEffect(()=>{
    let mounted=true
    let confirmed=false
    const sync=()=>{
      const api=desktopApi()
      if(!api)return
      void api.window_control("state").then(state=>{
        if(!mounted)return
        confirmed=true
        setConnected(true)
        setMaximized(state.maximized)
      }).catch(()=>{
        if(mounted)setConnected(false)
      })
    }
    sync()
    const retry=window.setInterval(()=>{if(!confirmed)sync()},750)
    window.addEventListener("pywebviewready",sync)
    window.addEventListener("focus",sync)
    return()=>{
      mounted=false
      window.clearInterval(retry)
      window.removeEventListener("pywebviewready",sync)
      window.removeEventListener("focus",sync)
    }
  },[])

  const act=async(action:WindowAction)=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(action)
    try{
      const state=await api.window_control(action)
      setMaximized(state.maximized)
    }catch{
      // Uma falha da API não deve simular que a ação ocorreu.
      setConnected(false)
    }finally{
      setBusy(null)
    }
  }

  const common="inline-flex h-9 w-10 items-center justify-center rounded-md border border-transparent text-muted transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-40"
  const disabled=!connected||busy!==null
  return <div className="flex shrink-0 items-center gap-0.5 border-l border-line/60 pl-2"
    role="group" aria-label="Controles da janela">
    <button type="button" title="Minimizar" aria-label="Minimizar janela"
      disabled={disabled} onClick={()=>void act("minimize")}
      className={common+" hover:bg-primary/10 hover:text-white"}>
      <Minus className="size-[17px]" strokeWidth={1.8}/>
    </button>
    <button type="button" title={maximized?"Restaurar janela":"Maximizar janela"}
      aria-label={maximized?"Restaurar janela":"Maximizar janela"}
      disabled={disabled} onClick={()=>void act("toggle_maximize")}
      className={common+" hover:bg-primary/10 hover:text-white"}>
      {maximized?<Copy className="size-[15px]" strokeWidth={1.75}/>:
        <Square className="size-[15px]" strokeWidth={1.8}/>}
    </button>
    <button type="button" title="Fechar DUELTRACE" aria-label="Fechar DUELTRACE"
      disabled={disabled} onClick={()=>void act("close")}
      className={common+" hover:border-danger/40 hover:bg-danger/85 hover:text-white"}>
      <X className="size-[19px]" strokeWidth={1.8}/>
    </button>
  </div>
}
