"use client"

import {useEffect,useState} from "react"
import {Gamepad2} from "lucide-react"
import {desktopApi,type EmulatorMode,type EmulatorStatus} from "@/lib/desktop"

export function EmulatorSettings(){
  const [status,setStatus]=useState<EmulatorStatus|null>(null)
  const [mode,setMode]=useState<EmulatorMode>("auto")
  const [port,setPort]=useState("8080")
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState("")
  useEffect(()=>{
    let alive=true
    desktopApi()?.get_emulator_status().then(result=>{
      if(!alive)return
      setStatus(result);setMode(result.mode);setPort(String(result.port))
    }).catch(()=>{if(alive)setError("Diagnóstico do emulador indisponível.")})
    return()=>{alive=false}
  },[])
  const operate=async(action:"save"|"select"|"check")=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true);setError("")
    try{
      if(action==="save")await api.set_emulator(mode,Number(port))
      if(action==="select")await api.configure_pcsx_redux()
      const data=await api.get_emulator_status()
      setStatus(data);setMode(data.mode);setPort(String(data.port))
    }catch(e){
      setError(e instanceof Error?e.message:"Não foi possível configurar PCSX-Redux.")
    }finally{setBusy(false)}
  }
  const portNumber=Number(port)
  const portOk=Number.isInteger(portNumber)&&portNumber>=1024&&portNumber<=65535
  return <section className="panel rounded-xl p-4 sm:p-5">
    <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-white">
      <Gamepad2 className="size-5 text-primary"/> Emulador do PlayStation 1
    </h2>
    <p className="mb-3 text-sm text-muted">
      O DUELTRACE Windows suporta ePSXe e PCSX-Redux. O PCSX-Redux utiliza sua API
      HTTP nativa para consultar a RAM emulada, sem varrer endereços do processo Windows.
    </p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="flex flex-col gap-2 text-sm text-muted">
        Emulador preferido
        <select className="field w-full p-3 text-white" value={mode}
          onChange={event=>setMode(event.target.value as EmulatorMode)} disabled={busy}>
          <option value="auto">Automático (ePSXe primeiro)</option>
          <option value="epsxe">ePSXe</option>
          <option value="pcsx-redux">PCSX-Redux</option>
        </select>
      </label>
      <label className="flex flex-col gap-2 text-sm text-muted">
        Porta HTTP local PCSX-Redux
        <input type="number" min={1024} max={65535}
          className="field w-full p-3 text-white" value={port}
          onChange={event=>setPort(event.target.value)} disabled={busy}/>
      </label>
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <button type="button" className="btn-gold" onClick={()=>void operate("save")}
        disabled={busy||!desktopApi()||!portOk}>Salvar emulador</button>
      <button type="button" className="btn-ghost" onClick={()=>void operate("select")}
        disabled={busy||!desktopApi()}>Selecionar PCSX-Redux.exe</button>
      <button type="button" className="btn-ghost" onClick={()=>void operate("check")}
        disabled={busy||!desktopApi()}>Verificar conexão</button>
    </div>
    <p className="mt-3 text-sm text-primary" role="status">
      {status?.status??"Verificando emuladores instalados…"}
    </p>
    <p className="mt-1 text-xs text-muted">
      Ativo: {status?.active==="pcsx-redux"?"PCSX-Redux":"ePSXe"} ·
      Servidor Redux: {status?.reduxAvailable?"acessível":"não encontrado"} ·
      Executável Redux: {status?.pcsxReduxConfigured?"configurado":"não configurado"}
    </p>
    <p className="mt-3 rounded border border-gold/35 p-3 text-xs text-gold">
      O DUELTRACE tenta primeiro a API nativa do PCSX-Redux. Se ela não
      estiver disponível, usa uma busca conservadora da RAM do processo Windows,
      sem alterar o jogo. Para usar HTTP, ative Configuration → Emulation →
      Enable Web Server. Esse servidor também oferece operações de escrita
      e pode ficar exposto à rede: restrinja a porta no Firewall do Windows.
      O DUELTRACE envia somente GET e nunca altera a RAM ou saves.
    </p>
    {error&&<p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
  </section>
}
