"use client"

import {useEffect,useState} from "react"
import {Calculator,RefreshCcw,Swords,X,ExternalLink} from "lucide-react"
import {desktopApi,useDesktopState} from "@/lib/desktop"
import type {HandState,RankState,SpoilsCounters,SpoilsResult} from "@/lib/desktop"

const CRITERIA:Array<{key:keyof SpoilsCounters;label:string}>= [
  {key:"turns",label:"Turnos"},
  {key:"effective_attacks",label:"Ataques efetivos"},
  {key:"defense_wins",label:"Vitórias em defesa"},
  {key:"face_down",label:"Cartas viradas para baixo"},
  {key:"spells",label:"Magias"},
  {key:"traps",label:"Armadilhas"},
  {key:"cards_used",label:"Cartas usadas"},
  {key:"remaining_lp",label:"LP restantes"},
  {key:"fusions",label:"Fusões realizadas"},
  {key:"equips",label:"Equipamentos"},
]
const EMPTY:SpoilsCounters={
  turns:0,effective_attacks:0,defense_wins:0,face_down:0,
  spells:0,traps:0,cards_used:0,remaining_lp:8000,
  fusions:0,equips:0,
}

function Head({name,kind}:{name:string;kind:"calculadora"|"fusoes"}){
  const [error,setError]=useState("")
  return <div className="mb-3 flex items-center justify-between gap-2">
    <div>
      <p className="font-display text-lg font-semibold text-gold">{name}</p>
      <p className="text-[11px] text-muted">Janela independente · DUELTRACE Alpha</p>
    </div>
    <button type="button" className="btn-ghost px-2 py-2" aria-label="Fechar ferramenta"
      onClick={async()=>{
        try{await desktopApi()?.close_tool_window(kind)}
        catch{setError("Use o X da janela para fechar.")}
      }}><X className="size-4"/></button>
    {error&&<p className="text-xs text-danger">{error}</p>}
  </div>
}

export function FloatingCalculator(){
  const {state}=useDesktopState()
  const [live,setLive]=useState<RankState|null>(null)
  const [fields,setFields]=useState<SpoilsCounters>(EMPTY)
  const [victory,setVictory]=useState<"lp"|"deckout"|"exodia">("lp")
  const [result,setResult]=useState<SpoilsResult|null>(null)
  const [error,setError]=useState("")
  const [busy,setBusy]=useState(false)

  useEffect(()=>{
    let mounted=true
    let requesting=false
    const update=async()=>{
      const api=desktopApi()
      if(!api||requesting)return
      requesting=true
      try{
        const value=await api.get_rank_auto()
        if(mounted)setLive(value)
      }catch{if(mounted)setLive(null)}
      finally{requesting=false}
    }
    void update()
    const interval=window.setInterval(()=>void update(),1300)
    return()=>{mounted=false;window.clearInterval(interval)}
  },[state?.activeSha])

  const calculate=async()=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true);setError("")
    try{setResult(await api.calculate_spoils(fields,victory))}
    catch(e){setError(e instanceof Error?e.message:"Cálculo indisponível.")}
    finally{setBusy(false)}
  }

  return <div className="mx-auto max-w-lg">
    <Head name="Calculadora de SPOILS" kind="calculadora"/>
    <p className="mb-2 truncate text-xs text-muted">
      ISO ativa: {state?.activeName??"Nenhuma"}
    </p>
    <section className="panel p-3">
      <p className="font-semibold text-primary"><Calculator className="mr-2 inline size-4"/>RANK ao vivo</p>
      <div className="mt-3 flex items-center justify-center gap-3 text-center">
        <strong className="font-display text-3xl text-gold">
          {live?.ready?live.score:"—"}
        </strong>
        <span className="font-display text-lg text-primary">
          {live?.ready?live.category:"Aguardando leitura"}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted">
        {live?.status??"Abra um duelo e selecione uma ISO compatível."}
      </p>
    </section>
    <section className="panel mt-3 p-3">
      <p className="mb-2 font-semibold text-gold">Calculadora manual</p>
      <div className="grid grid-cols-2 gap-2">
        {CRITERIA.map(item=><label key={item.key} className="text-xs text-muted">
          {item.label}
          <input className="field mt-1 w-full px-2 py-2 tabular-nums"
            type="number" inputMode="numeric" min={0}
            max={item.key==="remaining_lp"?32766:255} value={fields[item.key]}
            onChange={e=>{
              const cap=item.key==="remaining_lp"?32766:255
              const n=Number(e.target.value)
              setFields(v=>({...v,[item.key]:Number.isFinite(n)?
                Math.max(0,Math.min(cap,Math.trunc(n))):0}))
              setResult(null)
            }}/>
        </label>)}
      </div>
      <label className="mt-3 block text-xs text-muted">
        Resultado do duelo
        <select className="field mt-1 w-full p-2" value={victory}
          onChange={e=>{setVictory(e.target.value as typeof victory);setResult(null)}}>
          <option value="lp">Vitória por LP</option>
          <option value="deckout">Vitória por deck-out</option>
          <option value="exodia">Vitória por Exodia</option>
        </select>
      </label>
      <button type="button" className="btn-gold mt-3 w-full"
        disabled={busy||!desktopApi()} onClick={()=>void calculate()}>
        <RefreshCcw className="size-4"/>{busy?"Calculando…":"Calcular SPOILS"}
      </button>
      {error&&<p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
      {result&&<div className="mt-3 rounded-lg border border-gold/50 p-3">
        <div className="flex items-center justify-between">
          <strong className="font-display text-3xl text-gold">{result.score} pts</strong>
          <strong className="text-xl text-primary">{result.category}</strong>
        </div>
        <p className="mt-2 text-xs text-muted">{result.note}</p>
      </div>}
    </section>
    <p className="mt-3 text-center text-[11px] text-muted">
      Estimativas não substituem o RANK mostrado pelo jogo.
    </p>
  </div>
}

export function FloatingFusionTips(){
  const {state}=useDesktopState()
  const [hand,setHand]=useState<HandState|null>(null)
  const [mode,setMode]=useState<"pairs"|"chains">("pairs")
  const [error,setError]=useState("")
  const [expanded,setExpanded]=useState(false)

  useEffect(()=>{
    let mounted=true
    let requesting=false
    const load=async()=>{
      const api=desktopApi()
      if(!api||requesting)return
      requesting=true
      try{const next=await api.get_hand();if(mounted)setHand(next)}
      catch(e){if(mounted)setError(e instanceof Error?e.message:"Falha ao ler mão.")}
      finally{requesting=false}
    }
    void load()
    const timer=window.setInterval(()=>void load(),1500)
    return()=>{mounted=false;window.clearInterval(timer)}
  },[state?.activeSha])

  const pairs=hand?.pairs??[]
  const chains=hand?.chains??[]
  const count=mode==="pairs"?pairs.length:chains.length
  return <div className="mx-auto max-w-lg">
    <Head name="Dicas de fusões" kind="fusoes"/>
    <p className="mb-3 truncate text-xs text-muted">ISO: {state?.activeName??"Nenhuma selecionada"}</p>
    <div className="panel p-3">
      <p className="mb-2 text-sm text-primary">
        <Swords className="mr-2 inline size-4"/>
        {hand?.ready?"Mão conectada":"Aguardando mão"}
      </p>
      <div className="flex gap-2">
        <button type="button" className={mode==="pairs"?"btn-gold":"btn-ghost"}
          onClick={()=>{setMode("pairs");setExpanded(false)}}>Duplas</button>
        <button type="button" className={mode==="chains"?"btn-gold":"btn-ghost"}
          onClick={()=>{setMode("chains");setExpanded(false)}}>Cadeias (2–5)</button>
      </div>
      <p className="mt-3 text-xs text-muted">{hand?.status??"Abra um duelo no ePSXe."}</p>
      {error&&<p role="alert" className="text-xs text-danger">{error}</p>}
      {hand?.ready&&count===0&&<p className="mt-3 text-sm text-muted">
        Nenhuma fusão reconhecida para a mão atual.
      </p>}
      <div className="mt-3 space-y-2">
        {hand?.ready&&mode==="pairs"&&pairs.slice(0,expanded?24:8).map((item,i)=>
          <div key={i} className="rounded-md border border-line/70 p-3">
            <p className="text-xs text-primary">Posições {item.slot_a} + {item.slot_b}</p>
            <p className="font-semibold text-gold">{item.result_name} #{item.result}</p>
          </div>)}
        {hand?.ready&&mode==="chains"&&chains.slice(0,expanded?16:8).map((item,i)=>
          <div key={i} className="rounded-md border border-line/70 p-3">
            <p className="font-semibold text-gold">{item.result_name} #{item.result}</p>
            <p className="mt-1 text-xs text-primary">Ordem: {item.slot_order.join(" → ")}</p>
            <p className="mt-1 text-xs text-muted">
              {item.steps.map(x=>`#${x.material_a} + #${x.material_b} = #${x.result}`).join(" · ")}
            </p>
          </div>)}
      </div>
      {hand?.ready&&count>8&&<button type="button"
        className="btn-ghost mt-3 w-full" onClick={()=>setExpanded(v=>!v)}>
        {expanded?"Mostrar menos":`Mostrar todas (${count})`}
      </button>}
      {hand?.ready&&hand.chainsComplete===false&&mode==="chains"&&
        <p className="mt-2 text-xs text-gold">Busca parcial — limite de combinações atingido.</p>}
    </div>
    <p className="mt-3 text-center text-xs text-muted">
      Fusões extraídas da ISO podem estar pendentes de validação em jogo.
      A janela permanece independente quando o DUELTRACE é minimizado.
    </p>
  </div>
}
