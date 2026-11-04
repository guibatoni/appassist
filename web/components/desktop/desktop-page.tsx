"use client"

import Image from "next/image"
import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, FilePlus2, Gamepad2,
  GitMerge, Layers, Play, RefreshCcw, Search, Shield, Swords, Upload,
} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi, sourceLabel, useDesktopState} from "@/lib/desktop"
import {DropsPage} from "./drops-page"
import type {LocalCard, HandState, FusionPage, LocalMod, RankState, RankDiagnostic, SpoilsCounters, SpoilsResult} from "@/lib/desktop"

type Page = "inicio" | "mods" | "biblioteca" | "fusoes" | "drops"

function Heading({title,subtitle}:{title:string;subtitle:string}) {
  return <div className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-5 py-4">
    <h1 className="font-display text-2xl font-bold text-gold sm:text-3xl">{title}</h1>
    <p className="mt-1 text-sm text-muted">{subtitle}</p>
  </div>
}

function CardThumbnail({card,sha}:{card:LocalCard|null;sha:string|null}) {
  const [source,setSource]=useState<"composite"|"large"|"none">("composite")
  useEffect(()=>setSource("composite"),[sha,card?.id])
  const framed=card?cardWithFrame(sha,card.id):null
  const large=card?cardArt(sha,card.id):null
  const url=source==="composite"?framed:source==="large"?large:null
  return <div className={"relative mx-auto flex w-full max-w-32 items-center justify-center overflow-hidden bg-[#061126] shadow-[0_0_18px_rgb(56_200_255/0.18)] "+
      (source==="composite"
        ? "aspect-[52/60] rounded-sm border border-gold/20"
        : "aspect-[102/96] rounded-lg border border-line/50 p-1")}>
    {url?<Image src={url} alt={card?.name??""} fill unoptimized sizes="160px"
      className={source==="composite"?"object-fill [image-rendering:pixelated]":"object-contain p-1"}
      onError={()=>setSource(source==="composite"?"large":"none")}/>:
      <Layers className="size-9 text-primary/45" aria-label="Imagem não extraída"/>}
    {card&&<span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[10px] text-gold">#{card.id}</span>}
  </div>
}

function MonsterStats({card,className=""}:{card:LocalCard|null;className?:string}) {
  if (!card || card.category!=="Monstros") return null
  return <p className={"text-[11px] font-semibold tabular-nums text-primary "+className}>
    ATK {card.atk??"—"} · DEF {card.def??"—"}
  </p>
}

function Empty({children}:{children:React.ReactNode}) {
  return <p className="rounded-lg border border-line/60 bg-[#06152c]/70 px-4 py-6 text-center text-sm text-muted">{children}</p>
}

function RankPanel({sha}:{sha:string|null}) {
  const [rank,setRank]=useState<RankState|null>(null)
  const [lp,setLp]=useState("")
  const [busy,setBusy]=useState(false)
  const [captured,setCaptured]=useState<{score:number|null;category:string|null;status:string}|null>(null)
  const [captureBusy,setCaptureBusy]=useState(false)
  const [captureError,setCaptureError]=useState<string|null>(null)
  const [diagnostic,setDiagnostic]=useState<RankDiagnostic|null>(null)
  const [diagnosing,setDiagnosing]=useState(false)
  const [diagnosticError,setDiagnosticError]=useState<string|null>(null)
  useEffect(()=>{
    let mounted=true,busyRead=false
    setRank(null)
    setCaptured(null)
    setDiagnostic(null)
    setDiagnosticError(null)
    void desktopApi()?.get_pending_rank_capture().then(x=>{if(mounted&&x.ready)setCaptured(x)}).catch(()=>{})
    const refresh=async()=>{
      const api=desktopApi()
      if(!api||busyRead)return
      busyRead=true
      try{const result=await api.get_rank();if(mounted)setRank(result)}
      catch{if(mounted)setRank({ready:false,state:"unavailable",status:"Leitura de RANK indisponível",score:null,category:null,counters:null})}
      finally{busyRead=false}
    }
    void refresh()
    const id=window.setInterval(()=>void refresh(),2200)
    return()=>{mounted=false;window.clearInterval(id)}
  },[sha])
  const confirm=async()=>{
    if(!/^\d{1,5}$/.test(lp))return
    const value=Number(lp)
    if(!Number.isInteger(value)||value<0||value>32766)return
    const api=desktopApi()
    if(!api)return
    setBusy(true)
    try{setRank(await api.confirm_rank_lp(value))}
    catch{setRank({ready:false,state:"unavailable",status:"Não foi possível confirmar os LP",score:null,category:null,counters:null})}
    finally{setBusy(false)}
  }
  const diagnose=async()=>{
    const api=desktopApi()
    if(!api)return
    setDiagnosing(true)
    setDiagnosticError(null)
    try{setDiagnostic(await api.get_rank_diagnostic())}
    catch(e){
      setDiagnosticError(e instanceof Error?e.message:"Não foi possível consultar o perfil da ISO.")
    }finally{setDiagnosing(false)}
  }
  const capture=async()=>{
    const api=desktopApi()
    if(!api)return
    setCaptureBusy(true)
    setCaptureError(null)
    try{
      const result=await api.capture_rank_prediction()
      setCaptured(result)
    }catch(e){
      setCaptured(null)
      setCaptureError(e instanceof Error?e.message:"Não foi possível capturar a previsão.")
    }finally{setCaptureBusy(false)}
  }
  return <>
  <section className="panel rounded-xl p-4" aria-label="Contador de RANK">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="font-display text-xl font-semibold text-gold">Contador de RANK</h2>
        <p className="mt-1 text-xs text-muted">Projeção de pontuação · somente leitura</p>
      </div>
      <div className="flex min-w-36 items-baseline justify-end gap-2 rounded-lg border border-gold/30 bg-gradient-to-r from-[#152c4a] to-background px-3 py-2">
        <span className="font-display text-3xl font-bold tabular-nums text-primary">{rank?.ready?rank.score:"—"}</span>
        <span className="text-xs text-muted">pontos</span>
      </div>
    </div>
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
      <span className="rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-sm font-semibold text-primary">
        {rank?.ready?rank.category:"RANK indisponível"}
      </span>
      {rank?.ready&&<span className="text-xs text-gold">Estimativa · {rank.rankSystem==="x15"?"RANK X15":rank.rankSystem==="classic"?"RANK original":"RANK não identificado"} · não é resultado final</span>}
    </div>
    <p className="mt-2 text-sm text-muted" role="status">{rank?.status??"Consultando leitura e modelo do mod…"}</p>
    {(rank?.state==="needs_lp_confirmation"||rank?.state==="lp_mismatch")&&
      <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-line/60 bg-panel-strong/60 p-3">
        <label className="flex flex-col gap-1 text-xs text-foreground">
          LP atuais mostrados no jogo
          <input type="number" min={0} max={32766} inputMode="numeric"
            value={lp} onChange={e=>setLp(e.target.value)}
            className="field w-44 rounded-md px-3 py-2 text-sm" placeholder="Ex.: 8000"/>
        </label>
        <button type="button" className="btn-gold disabled:opacity-40" disabled={busy||!lp||!desktopApi()}
          onClick={()=>void confirm()}>Confirmar LP</button>
        <span className="text-xs text-muted">Candidato da RAM: {rank?.candidateLp??"—"} LP</span>
      </div>}
    {rank?.ready&&rank.counters&&
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted sm:grid-cols-4">
        {[["Turnos",rank.counters.turns??"—"],["Fusões",rank.counters.fusions??"—"],
          ["Magias",rank.counters.spells??"—"],["LP",rank.counters.remaining_lp??"—"]].map(([label,value])=>
          <div key={label} className="rounded-md border border-line/50 bg-background/40 px-3 py-2">
            <span className="block">{label}</span><strong className="font-display text-base text-white">{value??"—"}</strong>
          </div>)}
      </div>}
    <div className="mt-3 rounded-lg border border-primary/30 bg-background/40 p-3">
      <p className="text-xs font-semibold text-primary">Conferência com o resultado real</p>
      <p className="mt-1 text-xs text-muted">
        No final do duelo, a previsão de LP pode ser capturada para futura auditoria.
        O painel de Spoils abaixo acompanha automaticamente a leitura RAM quando validada.
      </p>
      <button type="button" disabled={!rank?.ready||captureBusy||!desktopApi()}
        className="btn-gold mt-2 disabled:opacity-40" onClick={()=>void capture()}>
        {captureBusy?"Capturando…":"Capturar previsão de RANK"}
      </button>
      {captured&&<p className="mt-2 text-xs text-primary" role="status">
        {captured.status} · {captured.score} pontos · {captured.category}
      </p>}
      {captureError&&<p className="mt-2 text-xs text-danger" role="alert">{captureError}</p>}
      {!rank?.ready&&<div className="mt-3 border-t border-line/60 pt-3">
        <p className="text-xs text-muted">
          A captura precisa de uma previsão autorizada. Não é possível
          habilitá-la apenas por nome do mod ou por uma tabela MIPS estática.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button type="button" className="btn-ghost disabled:opacity-40"
            disabled={diagnosing||!sha||!desktopApi()} onClick={()=>void diagnose()}>
            {diagnosing?"Investigando…":"Diagnosticar RANK desta ISO"}
          </button>
        </div>
        {diagnosticError&&<p className="mt-2 text-xs text-danger" role="alert">{diagnosticError}</p>}
        {diagnostic&&<div className="mt-3 rounded-lg border border-gold/30 bg-background/50 p-3 text-xs" role="status">
          <p className="font-semibold text-gold">Diagnóstico da ISO {diagnostic.isoShaPrefix??"não selecionada"}{diagnostic.isoShaPrefix?"…":""}</p>
          <p className="mt-1 text-foreground">{diagnostic.reason}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-muted sm:grid-cols-3">
            <span>Tabela WA: {diagnostic.rankTableDetected?"Detectada":"Não identificada"}</span>
            <span>Estrutura WA: {diagnostic.rankStructureVerified?"Conferida":"Pendente"}</span>
            <span>PCs candidatos: {diagnostic.mipsCandidates}</span>
            <span>RAM validada: {diagnostic.ramBindingVerified?"Sim":"Não"}</span>
            <span>Modelo X15 idêntico: {diagnostic.x15Exact||diagnostic.x15CompatibleBinary?"Sim":"Não"}</span>
            <span>Projeção habilitada: {diagnostic.readyForLiveRead?"Modelo autorizado":"Não"}</span>
          </div>
          <p className="mt-2 text-primary">Próxima ação: {diagnostic.nextStep}</p>
          <p className="mt-2 text-muted">{diagnostic.note}</p>
        </div>}
      </div>}
    </div>
    <p className="mt-3 text-xs text-muted">
      Esta atualização mantém a fórmula de pontos já usada pelo DUELTRACE e altera apenas a letra
      exibida segundo o sistema da ISO ativa (X15 ou original). A leitura ao vivo requer RAM calibrada
      e LP confirmados; mods sem mapeamento validado continuam indisponíveis.
    </p>
  </section>
  <SpoilsCalculator sha={sha} liveRank={rank}/>
  </>
}

const SPOILS_FIELDS: Array<{key:keyof SpoilsCounters;label:string}> = [
  {key:"turns",label:"Turnos"},
  {key:"effective_attacks",label:"Monstros adversários destruídos em ataque"},
  {key:"defense_wins",label:"Vitórias em defesa"},
  {key:"face_down",label:"Cartas colocadas viradas para baixo"},
  {key:"spells",label:"Magias utilizadas"},
  {key:"traps",label:"Armadilhas ativadas"},
  {key:"cards_used",label:"Cartas usadas ou sacadas"},
  {key:"remaining_lp",label:"LP restantes"},
  {key:"fusions",label:"Fusões iniciadas"},
  {key:"equips",label:"Equipamentos utilizados"},
]
const SPOILS_DEFAULTS: SpoilsCounters = {
  turns:0,effective_attacks:0,defense_wins:0,face_down:0,spells:0,
  traps:0,cards_used:0,remaining_lp:8000,fusions:0,equips:0,
}

function SpoilsCalculator({sha,liveRank}:{sha:string|null;liveRank:RankState|null}) {
  const [baseline,setBaseline]=useState<SpoilsResult|null>(null)
  const [baselineError,setBaselineError]=useState<string|null>(null)
  // Não duplicar a fórmula no JavaScript: calculadora Python existente fornece a referência.
  useEffect(()=>{
    let mounted=true
    setBaseline(null)
    setBaselineError(null)
    const api=desktopApi()
    if(!sha||!api)return()=>{mounted=false}
    void api.calculate_spoils({...SPOILS_DEFAULTS},"lp")
      .then(result=>{if(mounted)setBaseline(result)})
      .catch(()=>{if(mounted)setBaselineError("Referência inicial indisponível.")})
    return()=>{mounted=false}
  },[sha])

  const live=liveRank?.ready===true &&
    liveRank.score!==null && liveRank.category!==null && liveRank.counters!==null
  const score=live?(liveRank?.score??null):baseline?.score??null
  const category=live?(liveRank?.category??null):baseline?.category??null
  const counters=live?(liveRank?.counters??SPOILS_DEFAULTS):SPOILS_DEFAULTS
  const breakdown=live?liveRank?.breakdown:baseline?.breakdown
  const pointsFor=(key:string)=>(breakdown as Record<string,number>|undefined)?.[key]
  const entries=live
    ? Object.entries(counters).filter(([key])=>pointsFor(key)!==undefined)
        .map(([key,value])=>({key,label:SPOILS_FIELDS.find(x=>x.key===key)?.label??key,value}))
    : SPOILS_FIELDS.map(({key,label})=>({key,label,value:SPOILS_DEFAULTS[key]}))

  return <section className="panel rounded-xl p-4" aria-label="Calculadora automática de Spoils">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="font-display text-xl font-semibold text-gold">Calculadora automática de Spoils</h2>
        <p className="mt-1 text-sm text-muted">
          Acompanha os contadores do ePSXe automaticamente quando existe leitura RAM validada
          e os LP do duelo foram confirmados. Não é necessário digitar os dez critérios.
        </p>
      </div>
      <div className="min-w-36 rounded-lg border border-gold/30 bg-background/60 px-4 py-3 text-right">
        <p className="text-xs text-muted">{live?"Projeção ao vivo (vitória por LP)":"Referência inicial, sem leitura do jogo"}</p>
        <p className="font-display text-3xl font-bold tabular-nums text-primary">
          {score??"—"} <span className="text-sm text-muted">pontos</span>
        </p>
        <p className="font-display text-lg font-semibold text-gold">{category??"RANK indisponível"}</p>
      </div>
    </div>
    <p className={"mt-3 text-xs font-semibold "+(live?"text-success":"text-gold")} role="status">
      {live
        ?"Leitura ativa: os pontos mudam automaticamente conforme os contadores do duelo."
        :"Abertura hipotética: 101 pontos, considerando 8.000 LP, zero ações e vitória futura por LP. NÃO é uma leitura do ePSXe."}
    </p>
    {!live&&<p className="mt-1 text-xs text-muted">
      {liveRank?.status??"Aguardando o ePSXe e o perfil da ISO."}
      {" "}Use a confirmação de LP no Contador de RANK acima se solicitada.
      Mods sem mapeamento verificado não terão pontuação ao vivo.
    </p>}
    {baselineError&&!live&&<p className="mt-2 text-xs text-danger" role="alert">{baselineError}</p>}
    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {entries.map(item=><div key={item.key}
        className="rounded-lg border border-line/60 bg-background/40 p-3">
        <p className="min-h-7 text-xs text-muted">{item.label}</p>
        <p className="mt-1 text-lg font-semibold tabular-nums text-white">
          {item.value}
          <span className="ml-2 text-xs font-normal text-primary">
            {pointsFor(item.key)!==undefined
              ? `${pointsFor(item.key)!>0?"+":""}${pointsFor(item.key)} pts`
              :"—"}
          </span>
        </p>
      </div>)}
    </div>
    <p className="mt-3 text-xs text-muted">
      Base da fórmula: 50. Com 8.000 LP, dez critérios no estado inicial
      e bônus hipotético de vitória por LP (+2), a projeção inicial é 101.
      Os critérios já contribuem para a pontuação de abertura.
    </p>
    <p className="mt-2 text-xs text-gold">
      Esta projeção supõe vitória por LP. O jogo pode terminar por deck-out ou Exodia;
      o resultado final e a ISO aberta no emulador ainda precisam ser confirmados.
    </p>
  </section>
}

function Home({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const [hand,setHand]=useState<HandState|null>(null)
  const [mode,setMode]=useState<"pairs"|"chains">("pairs")
  useEffect(()=>{
    let mounted=true,busy=false
    const load=async()=>{
      const api=desktopApi()
      if(!api||busy)return
      busy=true
      try{const x=await api.get_hand();if(mounted)setHand(x)}
      catch{if(mounted)setHand({ready:false,status:"Mão indisponível",hand:[],pairs:[],chains:[]})}
      finally{busy=false}
    }
    void load()
    const timer=window.setInterval(()=>void load(),1500)
    return()=>{mounted=false;window.clearInterval(timer)}
  },[sha])
  return <>
    <Heading title="Central de Duelo" subtitle="Sua mão, projeção de RANK e combinações do perfil ativo"/>
    <RankPanel sha={sha}/>
    <div className="panel rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl font-semibold text-primary">Sua mão · 5 slots</h2>
        <p className={hand?.ready?"text-xs text-success":"text-xs text-gold"}>{hand?.status??"Aguardando ePSXe"}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
        {Array.from({length:5},(_,slot)=>{
          const card=hand?.ready?hand.hand[slot]??null:null
          return <div key={slot} className="rounded-lg border border-line bg-gradient-to-b from-panel-strong to-background p-2.5">
            <p className="mb-2 text-center text-xs text-gold">SLOT {slot+1}</p>
            <CardThumbnail key={String(sha)+"-"+String(card?.id??"empty")} card={card} sha={sha}/>
            <p className="mt-2 min-h-9 text-center text-xs font-semibold text-white">{card?.name??"Aguardando carta"}</p>
            <MonsterStats card={card} className="text-center"/>
          </div>
        })}
      </div>
    </div>
    <div className="panel rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl text-gold">Fusões disponíveis</h2>
        <div className="flex gap-2">
          <button type="button" onClick={()=>setMode("pairs")} className={mode==="pairs"?"btn-gold":"btn-ghost"}>Duplas</button>
          <button type="button" onClick={()=>setMode("chains")} className={mode==="chains"?"btn-gold":"btn-ghost"}>Cadeias (2–5)</button>
        </div>
      </div>
      {!hand?.ready?<Empty>Entre em duelo no ePSXe. Nenhuma mão fictícia é exibida.</Empty>:
        mode==="pairs"?(hand.pairs.length?<div className="grid gap-2 lg:grid-cols-2">
          {hand.pairs.map((x,i)=><div key={i} className="rounded-lg border border-line/70 bg-panel-strong/60 p-3">
            <p className="text-xs text-primary">Slots {x.slot_a} + {x.slot_b}</p>
            <p className="mt-1 font-semibold text-white">{x.result_name} #{x.result}</p>
            <MonsterStats card={cardsById.get(x.result)??null} className="mt-1"/>
            <p className="mt-1 text-xs text-gold">{sourceLabel(x.validation)}</p>
          </div>)}</div>:<Empty>Não há fusões de duas cartas para a mão atual.</Empty>):
        (hand.chains.length?<div className="grid gap-3 lg:grid-cols-2">
          {hand.chains.map((x,i)=><div key={i} className="rounded-xl border border-gold/30 bg-gradient-to-r from-[#112746] to-panel p-3">
            <p className="font-semibold text-gold">{x.result_name} #{x.result}</p>
            <MonsterStats card={cardsById.get(x.result)??null} className="mt-1"/>
            <p className="mt-1 text-xs text-primary">Ordem: {x.slot_order.join(" → ")}</p>
            <ol className="mt-2 space-y-1 text-xs text-muted">{x.steps.map((s,j)=>
              <li key={j}>{j+1}. #{s.material_a} + #{s.material_b} = #{s.result} ({sourceLabel(s.validation)})</li>)}</ol>
          </div>)}</div>:<Empty>Nenhuma cadeia de 2 a 5 cartas foi identificada.</Empty>)}
      {hand?.chainsComplete===false&&mode==="chains"&&<p className="mt-2 text-xs text-gold">Busca parcial; o limite de estados foi alcançado.</p>}
      <p className="mt-3 text-xs text-muted">Resultados extraídos do mod. O jogo ainda precisa confirmar as combinações em duelo.</p>
    </div>
  </>
}

function Mods({mods,sha,onRefresh,configured}:{
  mods:LocalMod[];sha:string|null;onRefresh:()=>Promise<void>;configured:boolean
}) {
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState<string|null>(null)
  const rescan=async(mod:LocalMod)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true);setMessage(null)
    try{
      const result=await api.scan_sources(mod.sha256)
      await onRefresh()
      setMessage("ISO analisada: "+result.opponentCount+" oponentes, "+result.dropEntries+" drops, "+result.artCount+" artes, "+
        result.frameStyles+" molduras originais, "+result.framedCards+" cartas com moldura, "+
        result.descriptionCount+" descrições e "+
        result.effectTexts+" textos indicativos de efeitos. "+
        "A execução dos efeitos no jogo não foi confirmada.")
    }catch(e){
      setMessage(e instanceof Error?e.message:"Falha na análise local dos arquivos")
    }finally{setBusy(false)}
  }
  const run=async (action:()=>Promise<unknown>,label:string)=>{
    setBusy(true);setMessage(null)
    try{const result=await action();await onRefresh();setMessage(label)}
    catch(e){setMessage(e instanceof Error?e.message:"Operação não concluída")}
    finally{setBusy(false)}
  }
  return <>
    <Heading title="Biblioteca de Mods" subtitle="Importe e ative imagens locais, com dados separados por SHA da ISO"/>
    <section className="panel rounded-xl p-4">
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-gold disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.import_iso(),"Processamento de ISO concluído ou cancelado.")}>
          <FilePlus2 className="size-4"/> Importar ISO/BIN</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.configure_epsxe(),"Configuração do emulador atualizada.")}>
          <Gamepad2 className="size-4"/> {configured?"Alterar ePSXe.exe":"Configurar ePSXe.exe"}</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!configured||!sha||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.start_game(),"Comando enviado ao ePSXe.")}>
          <Play className="size-4"/> Iniciar jogo</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void run(async()=>{}, "Lista de mods atualizada. Para reler os arquivos da ISO, use 'Ler WA_MRG + SLUS novamente'.")}>
          <RefreshCcw className="size-4"/> Atualizar lista</button>
      </div>
      {message&&<p className="mt-3 text-sm text-gold" role="status">{message}</p>}
      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {mods.map(mod=><div key={mod.sha256} className={"rounded-xl border bg-gradient-to-b from-panel-strong/90 to-panel/50 p-4 "+(sha===mod.sha256?"border-success/70":"border-line/70")}>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0">
            <p className="truncate font-semibold text-white">{mod.name}</p>
            <p className="mt-1 text-xs text-muted">{mod.sha256.slice(0,18)}…</p>
          </div><span className={sha===mod.sha256?"text-xs text-success":"text-xs text-gold"}>{sha===mod.sha256?"Ativo":mod.requiresReview?"Revisão necessária":"Conhecido"}</span></div>
          <div className="my-4 grid grid-cols-2 gap-2 text-center sm:grid-cols-3 xl:grid-cols-3">
            {([["Cartas",mod.cards],["Oponentes",mod.opponents??0],["Drops",mod.dropEntries??0],
              ["Fusões",mod.fusions],["Textos de efeito",mod.effects],["Descrições",mod.descriptions??0],
              ["Tabelas WA",mod.dropTables??0],["Molduras WA",mod.frameStyles??0],
              ["Cartas emolduradas",mod.framedCards??0]] as const).map(([label,n])=>
              <div key={label} className="rounded-lg border border-line/50 bg-background/70 p-2"><p className="font-display text-xl text-primary">{n}</p><p className="text-xs text-muted">{label}</p></div>)}
          </div>
          <p className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-muted">
            <span className="font-semibold text-primary">RANK automático: </span>
            {mod.rankBinaryVerified
              ? "Tabela e identidade do executável verificadas. A RAM ainda precisa de teste em duelo."
              : mod.rankDetected
                ? "Pontos encontrados no WA. O uso dessas regras pelo SLUS ainda está em investigação."
                : "Tabela de pontos não confirmada para este mod."}
            {mod.rankMipsCandidates ? <span className="ml-1"> · {mod.rankMipsCandidates} trechos MIPS candidatos (não confirmados)</span> : null}
            {mod.rankDetected&&typeof mod.rankOffset==="number"&&
              <span className="ml-1 tabular-nums">Offset WA: 0x{mod.rankOffset.toString(16).toUpperCase()}</span>}
          </p>
          <button type="button" disabled={busy||!desktopApi()||sha===mod.sha256}
            className="btn-gold w-full disabled:opacity-40" onClick={()=>{
              const ok=!mod.requiresReview||window.confirm("O mod requer revisão. Ativar somente os dados comprovados?")
              if(ok)void run(()=>desktopApi()!.activate_mod(mod.sha256,mod.requiresReview),"Perfil ativado.")
            }}>{sha===mod.sha256?"Perfil ativo":"Ativar perfil"}</button>
          <button type="button" className="btn-ghost mt-2 w-full disabled:opacity-40"
            disabled={busy||!desktopApi()}
            onClick={()=>void rescan(mod)}>
            <RefreshCcw className="size-4"/> Ler WA_MRG + SLUS novamente
          </button>
        </div>)}
      </div>
      {!mods.length&&<Empty>Nenhum mod cadastrado. Importe uma ISO/BIN na versão Windows. Os arquivos não são enviados ao Vercel.</Empty>}
    </section>
  </>
}

function Library({cards,sha}:{cards:LocalCard[];sha:string|null}) {
  const [search,setSearch]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"def"|"type"|"name">("id")
  const [cardType,setCardType]=useState("")
  const [page,setPage]=useState(0)
  const [selectedId,setSelectedId]=useState<number|null>(null)
  const types=useMemo(()=>Array.from(new Set(cards.map(c=>c.type||c.category).filter(Boolean))).sort((a,b)=>a.localeCompare(b,"pt-BR")),[cards])
  useEffect(()=>{setSearch("");setSort("id");setCardType("");setPage(0);setSelectedId(null)},[sha])
  const visible=useMemo(()=>{
    const q=search.trim().toLocaleLowerCase("pt-BR")
    const filtered=cards.filter(c=>(!q||(String(c.id)+" "+c.name+" "+c.type+" "+c.category).toLocaleLowerCase("pt-BR").includes(q))
      &&(!cardType||(c.type||c.category)===cardType))
    const stat=(a:LocalCard,b:LocalCard,key:"atk"|"def")=>{
      const av=a[key],bv=b[key]
      if(typeof av!=="number")return typeof bv!=="number"?a.id-b.id:1
      if(typeof bv!=="number")return -1
      return bv-av||a.id-b.id
    }
    filtered.sort((a,b)=>sort==="atk"?stat(a,b,"atk"):sort==="def"?stat(a,b,"def")
      :sort==="name"?a.name.localeCompare(b.name,"pt-BR")||a.id-b.id
      :sort==="type"?(a.type||a.category).localeCompare(b.type||b.category,"pt-BR")||a.name.localeCompare(b.name,"pt-BR")||a.id-b.id
      :a.id-b.id)
    return filtered
  },[cards,search,sort,cardType])
  const chosen=visible.find(c=>c.id===selectedId)??visible[0]??null
  const pages=Math.max(1,Math.ceil(visible.length/32))
  return <>
    <Heading title="Biblioteca de Cartas" subtitle="Cartas extraídas da ISO ativa, sem raridades e efeitos inventados"/>
    <section className="panel rounded-xl p-4">
      <div className="flex flex-wrap gap-2">
        <label className="field flex min-w-56 flex-1 items-center gap-2 px-3 py-2">
          <Search className="size-4 text-primary"/><span className="sr-only">Buscar carta</span>
          <input className="w-full bg-transparent outline-none" value={search}
            onChange={e=>{setSearch(e.target.value);setPage(0)}} placeholder="Buscar por nome, tipo ou ID"/>
        </label>
        <select className="field px-3 py-2" value={sort} aria-label="Ordenar" onChange={e=>{setSort(e.target.value as typeof sort);setPage(0)}}>
          <option value="id">ID</option><option value="atk">Maior ataque</option><option value="def">Maior defesa</option><option value="type">Tipo</option><option value="name">Alfabética (A–Z)</option>
        </select>
        <select className="field px-3 py-2" value={cardType} aria-label="Filtrar por tipo"
          onChange={e=>{setCardType(e.target.value);setPage(0)}}>
          <option value="">Todos os tipos</option>
          {types.map(t=><option key={t} value={t}>{t}</option>)}
        </select>
        <span className="self-center text-sm text-muted">{visible.length} / {cards.length} cartas</span>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {visible.slice(page*32,(page+1)*32).map(card=><button type="button" key={card.id}
              className={"rounded-lg border p-2 text-center transition hover:border-primary "+(chosen?.id===card.id?"border-primary bg-primary/10":"border-line/70 bg-panel-strong/60")}
              onClick={()=>setSelectedId(card.id)}>
              <CardThumbnail key={String(sha)+"-"+card.id} card={card} sha={sha}/>
              <p className="mt-2 min-h-9 text-xs font-semibold text-white">{card.name}</p>
              <MonsterStats card={card} className="mt-1 text-center"/>
            </button>)}
          </div>
          {!visible.length&&<Empty>Nenhuma carta identificada para esta pesquisa.</Empty>}
          <div className="mt-3 flex items-center justify-center gap-3">
            <button type="button" className="btn-ghost disabled:opacity-30" disabled={page===0} onClick={()=>setPage(x=>x-1)}><ChevronLeft className="size-4"/>Anterior</button>
            <span className="text-xs text-muted">{page+1} / {pages}</span>
            <button type="button" className="btn-ghost disabled:opacity-30" disabled={page+1>=pages} onClick={()=>setPage(x=>x+1)}>Próxima<ChevronRight className="size-4"/></button>
          </div>
        </div>
        <aside className="rounded-xl border border-gold/40 bg-gradient-to-b from-[#142b50] to-background p-4">
          {chosen?<><h2 className="font-display text-xl font-semibold text-gold">#{chosen.id} {chosen.name}</h2>
            <div className="my-4"><CardThumbnail key={String(sha)+"-"+chosen.id} card={chosen} sha={sha}/></div>
            <MonsterStats card={chosen} className="text-base"/>
            <p className="mt-2 text-sm text-muted">Tipo: {chosen.type||"Não identificado"}</p>
            <p className="text-sm text-muted">Categoria: {chosen.category}</p>
            {chosen.level!==null&&chosen.level!==undefined&&<p className="text-sm text-muted">Nível: {chosen.level} · Atributo ID: {chosen.attributeId??"—"}</p>}
            {(chosen.guardianStar1!==null&&chosen.guardianStar1!==undefined||chosen.guardianStar2!==null&&chosen.guardianStar2!==undefined)&&
              <p className="text-sm text-muted">Estrelas Guardiãs (IDs extraídos): {chosen.guardianStar1??"—"} / {chosen.guardianStar2??"—"}</p>}
            <div className="mt-4 rounded-lg border border-line/70 bg-background/60 p-3">
              <h3 className="mb-1 font-semibold text-gold">Descrição extraída do SLUS</h3>
              <p className="whitespace-pre-line text-sm text-foreground/85">{chosen.description??"Nenhuma descrição vinculada com segurança ao ID desta carta."}</p>
              {chosen.descriptionSource&&<p className="mt-2 break-all text-[11px] text-muted">Fonte: {chosen.descriptionSource}</p>}
            </div>
            <div className="mt-4 rounded-lg border border-line/70 bg-background/60 p-3">
              <h3 className="mb-1 font-semibold text-primary">Texto indicativo de efeito</h3>
              <p className="whitespace-pre-line text-sm text-foreground/85">{chosen.effect??"Nenhum efeito individual foi identificado com procedência."}</p>
              {chosen.effect&&<p className="mt-2 text-xs text-gold">
                Mecânica no duelo ainda não confirmada — descrição não é prova de execução.
              </p>}
              {chosen.effectSource&&<p className="mt-1 break-all text-xs text-muted">Fonte: {chosen.effectSource}</p>}
            </div></>:<Empty>Selecione uma carta.</Empty>}
        </aside>
      </div>
    </section>
  </>
}

function FusionIllustration({id,name,sha,card,role}:{
  id:number;name:string;sha:string|null;card:LocalCard|null;role:string
}) {
  const displayed:LocalCard=card??{
    id,name,type:"",attribute:"",category:"Não identificada",
    atk:null,def:null,effect:null,effectSource:null
  }
  return <div className="flex min-w-0 flex-col items-center gap-1.5" title={name}>
    <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{role}</span>
    <div className="w-16 sm:w-20">
      <CardThumbnail key={String(sha)+"-"+id} card={displayed} sha={sha}/>
    </div>
    <span className="text-center text-[11px] font-semibold text-gold">#{id}</span>
    <span className="line-clamp-2 min-h-8 break-words text-center text-xs font-medium text-foreground">{name}</span>
    <MonsterStats card={displayed} className="text-center text-[10px]"/>
  </div>
}

function Fusions({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const [query,setQuery]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"def"|"type"|"name">("id")
  const [cardType,setCardType]=useState("")
  const [offset,setOffset]=useState(0)
  const [records,setRecords]=useState<FusionPage|null>(null)
  const [error,setError]=useState<string|null>(null)
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const types=useMemo(()=>Array.from(new Set(cards.map(c=>c.type||c.category).filter(Boolean))).sort((a,b)=>a.localeCompare(b,"pt-BR")),[cards])
  useEffect(()=>{setQuery("");setSort("id");setCardType("");setOffset(0);setRecords(null)},[sha])
  const pageSize=12
  useEffect(()=>{
    let mounted=true
    setRecords(null)
    const id=window.setTimeout(async()=>{
      const api=desktopApi()
      if(!api){if(mounted)setRecords(null);return}
      try{
        const result=await api.get_fusions(query,offset,pageSize,sort,cardType)
        if(mounted){setRecords(result);setError(null)}
      }catch(e){if(mounted)setError(e instanceof Error?e.message:"Falha ao carregar fusões")}
    },220)
    return()=>{mounted=false;window.clearTimeout(id)}
  },[sha,query,offset,sort,cardType])
  return <>
    <Heading title="Biblioteca de Fusões" subtitle="Imagem, nome e ID de cada material e resultado — somente receitas do mod ativo"/>
    <section className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="field flex min-w-56 flex-1 items-center gap-2 px-3 py-2">
          <Search className="size-4 text-primary"/>
          <input className="w-full bg-transparent outline-none" placeholder="Pesquisar material, resultado ou ID"
            value={query} onChange={e=>{setQuery(e.target.value);setOffset(0)}}/>
        </label>
        <label className="text-xs text-muted">Ordenar resultado
          <select className="field ml-2 px-2 py-2 text-sm" value={sort}
            onChange={e=>{setSort(e.target.value as typeof sort);setOffset(0)}}>
            <option value="id">ID</option><option value="atk">Maior ataque</option>
            <option value="def">Maior defesa</option><option value="type">Tipo</option>
            <option value="name">Alfabética (A–Z)</option>
          </select>
        </label>
        <label className="text-xs text-muted">Tipo do resultado
          <select className="field ml-2 px-2 py-2 text-sm" value={cardType}
            onChange={e=>{setCardType(e.target.value);setOffset(0)}}>
            <option value="">Todos os tipos</option>
            {types.map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <span className="text-xs text-muted">{records?.total??0} receitas</span>
      </div>
      {error&&<p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {records?.rows.map((r,i)=><article key={r.a+"-"+r.b+"-"+r.result+"-"+i}
          className="rounded-xl border border-line/80 bg-gradient-to-br from-panel-strong/90 via-[#0b1a35] to-background p-3 shadow-[inset_0_1px_0_rgb(245_184_61/0.09)] transition-colors hover:border-primary/60">
          <div className="grid grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)] items-start gap-1">
            <FusionIllustration id={r.a} name={r.nameA} card={cardsById.get(r.a)??null} sha={sha} role="Material A"/>
            <span className="pt-14 text-center font-display text-xl font-bold text-primary" aria-hidden>+</span>
            <FusionIllustration id={r.b} name={r.nameB} card={cardsById.get(r.b)??null} sha={sha} role="Material B"/>
            <span className="pt-14 text-center font-display text-xl font-bold text-gold" aria-hidden>→</span>
            <FusionIllustration id={r.result} name={r.nameResult} card={cardsById.get(r.result)??null} sha={sha} role="Resultado"/>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line/50 pt-2">
            <span className="text-xs text-muted">#{r.a} + #{r.b} → #{r.result}</span>
            <MonsterStats card={cardsById.get(r.result)??null} className="text-sm"/>
          </div>
        </article>)}
      </div>
      {records&&!records.rows.length&&<Empty>Não há fusões cadastradas para esta pesquisa e este mod.</Empty>}
      {!records&&!error&&<p className="py-4 text-center text-sm text-muted">Carregando receitas do perfil ativo…</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted">
          {records?.total?String(offset+1)+"–"+Math.min(offset+pageSize,records.total)+" de "+records.total:"Nenhuma receita"}
        </p>
        <div className="flex gap-2">
          <button type="button" className="btn-ghost disabled:opacity-30" disabled={offset===0}
            onClick={()=>setOffset(x=>Math.max(0,x-pageSize))}>
            <ChevronLeft className="size-4"/> Anterior
          </button>
          <button type="button" className="btn-ghost disabled:opacity-30" disabled={offset+pageSize>=(records?.total??0)}
            onClick={()=>setOffset(x=>x+pageSize)}>Próxima <ChevronRight className="size-4"/></button>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        As imagens só aparecem quando o scanner extraiu PNGs da ISO ativa.
        Na ausência de arte, mostramos um cartão simbólico; nenhuma imagem é inventada.
      </p>
    </section>
  </>
}

export function DesktopPage({page}:{page:Page}) {
  const {state,error,loading,refresh}=useDesktopState()
  return <div className="flex flex-col gap-3 lg:gap-4">
    <div className="panel flex flex-wrap items-center gap-3 rounded-xl px-4 py-2 text-xs">

      <span className="text-muted">ISO ativa: <strong className="font-semibold text-white">{state?.activeName??"Nenhuma ISO selecionada"}</strong></span>
    </div>
    {error&&<p className="rounded-lg border border-gold/40 bg-gold/10 p-3 text-sm text-gold" role="status">{error}</p>}
    {loading&&<p className="text-sm text-muted">Carregando dados locais...</p>}
    {page==="inicio"&&<Home sha={state?.activeSha??null} cards={state?.cards??[]}/>}
    {page==="mods"&&<Mods mods={state?.mods??[]} sha={state?.activeSha??null} configured={Boolean(state?.epsxeConfigured)} onRefresh={refresh}/>}
    {page==="biblioteca"&&<Library sha={state?.activeSha??null} cards={state?.cards??[]}/>}
    {page==="fusoes"&&<Fusions sha={state?.activeSha??null} cards={state?.cards??[]}/>}
    {page==="drops"&&<DropsPage sha={state?.activeSha??null}/>}
  </div>
}
