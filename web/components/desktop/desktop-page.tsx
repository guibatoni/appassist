"use client"

import Image from "next/image"
import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, FilePlus2, Gamepad2,
  GitMerge, Layers, Play, RefreshCcw, Search, Shield, Swords, Upload,
} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi, useDesktopState} from "@/lib/desktop"
import {DropsPage} from "./drops-page"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"
import type {LocalCard, HandState, FusionPage, LocalMod, RankState, CardMatchResult, CardAIMatchReport, ModScanDiagnostic, CardDropSources} from "@/lib/desktop"

type Page = "inicio" | "mods" | "biblioteca" | "fusoes" | "drops"

function Heading({title,subtitle}:{title:string;subtitle:string}) {
  return <div className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-5 py-4">
    <h1 className="font-display text-2xl font-bold text-gold sm:text-3xl">{title}</h1>
    <p className="mt-1 text-sm text-muted">{subtitle}</p>
  </div>
}

function CardThumbnail({card,sha,expanded=false}:{card:LocalCard|null;sha:string|null;expanded?:boolean}) {
  const [source,setSource]=useState<"composite"|"large"|"none">("composite")
  useEffect(()=>setSource("composite"),[sha,card?.id])
  const framed=card?cardWithFrame(sha,card.id):null
  const large=card?cardArt(sha,card.id):null
  const url=source==="composite"?framed:source==="large"?large:null
  return <div className={"relative mx-auto flex w-full items-center justify-center overflow-hidden bg-[#061126] shadow-[0_0_18px_rgb(56_200_255/0.18)] "+
      (expanded?"max-w-48 ":"max-w-32 ")+
      (source==="composite"
        ? "aspect-[52/60] rounded-sm border border-gold/20"
        : "aspect-[102/96] rounded-lg border border-line/50 p-1")}>
    {url?<Image src={url} alt={card?.name??""} fill unoptimized sizes={expanded?"240px":"160px"}
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
  const [calibrating,setCalibrating]=useState(false)
  const [calibrationError,setCalibrationError]=useState(false)

  // Leitura automática continua ativa mesmo sem intervenção do usuário.
  useEffect(()=>{
    let mounted=true,reading=false
    setRank(null)
    setCalibrationError(false)
    const read=async()=>{
      const api=desktopApi()
      if(!api||reading)return
      reading=true
      try{
        const value=await api.get_rank_auto()
        if(mounted)setRank(value)
      }catch{
        if(mounted)setRank({ready:false,state:"unavailable",status:"",
          score:null,category:null,counters:null})
      }finally{reading=false}
    }
    void read()
    const interval=window.setInterval(()=>void read(),850)
    return()=>{mounted=false;window.clearInterval(interval)}
  },[sha])

  const calibrate=async()=>{
    const api=desktopApi()
    if(!api||!sha||calibrating)return
    setCalibrating(true)
    setCalibrationError(false)
    try{
      await api.calibrate_rank()
      setRank(await api.get_rank_auto())
    }catch{
      setCalibrationError(true)
    }finally{setCalibrating(false)}
  }

  const ready=rank?.ready===true
  return <section className="panel rounded-xl p-4" aria-label="RANK ao vivo">
    <div className="flex items-center justify-between gap-2">
      <h2 className="font-display text-lg font-semibold text-gold">RANK ao vivo</h2>
      <span className={"text-xs font-medium "+(ready?"text-success":"text-muted")}>
        {ready?"● Em tempo real":"○ Aguardando duelo"}
      </span>
    </div>
    <div className="mt-4 rounded-lg border border-primary/20 bg-background/60 px-4 py-5 text-center">
      <p className="font-display text-4xl font-bold tabular-nums text-primary">
        {ready?rank.score:"—"} <span className="text-sm font-normal text-muted">pts</span>
      </p>
      <p className="mt-2 font-display text-xl font-bold text-gold">
        {ready?rank.category:"—"}
      </p>
    </div>
    <button type="button" className="btn-ghost mt-4 w-full justify-center disabled:opacity-40"
      disabled={!sha||calibrating||!desktopApi()} onClick={()=>void calibrate()}>
      <RefreshCcw className={"size-4 "+(calibrating?"animate-spin":"")}/>
      {calibrating?"Calibrando…":"Calibrar calculadora"}
    </button>
    {calibrationError&&<p role="alert" className="mt-2 text-center text-xs text-gold">
      Não foi possível calibrar. Confira o mod selecionado.
    </p>}
  </section>
}

function Home({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const [hand,setHand]=useState<HandState|null>(null)
  const [mode,setMode]=useState<"pairs"|"chains">("pairs")
  const [showAll,setShowAll]=useState(false)
  useEffect(()=>{
    let mounted=true,reading=false
    setHand(null)
    const load=async()=>{
      const api=desktopApi()
      if(!api||reading)return
      reading=true
      try{const value=await api.get_hand();if(mounted)setHand(value)}
      catch{if(mounted)setHand({ready:false,status:"Mão indisponível",hand:[],pairs:[],chains:[]})}
      finally{reading=false}
    }
    void load()
    const interval=window.setInterval(()=>void load(),1500)
    return()=>{mounted=false;window.clearInterval(interval)}
  },[sha])
  useEffect(()=>setShowAll(false),[mode,sha])
  const combinations=mode==="pairs"?hand?.pairs??[]:hand?.chains??[]
  const visibleCombinations=showAll?combinations:combinations.slice(0,6)
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-2 px-1">
      <div>
        <h1 className="font-display text-2xl font-bold text-gold">Central de Duelo</h1>
        <p className="text-xs text-muted">Mão atual, fusões sugeridas e RANK ao vivo</p>
      </div>
      <span className={hand?.ready?"text-xs font-medium text-success":"text-xs text-muted"}>
        {hand?.ready?"● Mão conectada":"○ "+(hand?.status??"Aguardando ePSXe")}
      </span>
    </div>
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_290px]">
      <section className="panel min-w-0 rounded-xl p-4" aria-label="Cartas na mão">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h2 className="font-display text-lg font-semibold text-primary">Cartas na mão</h2>
          <span className="text-xs text-muted">5 posições · leitura automática</span>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({length:5},(_,slot)=>{
            const card=hand?.ready?hand.hand[slot]??null:null
            return <div key={slot}
              className="min-w-0 rounded-lg border border-line/60 bg-background/50 px-2 py-3">
              <p className="mb-2 text-center text-[11px] text-gold">{slot+1}</p>
              <CardThumbnail card={card} sha={sha}/>
              <p className="mt-2 min-h-8 break-words text-center text-xs font-semibold text-white">
                {card?.name??"Aguardando"}
              </p>
              <MonsterStats card={card} className="text-center"/>
            </div>
          })}
        </div>
        {!hand?.ready&&<p className="mt-3 text-center text-xs text-muted">
          Abra um duelo no ePSXe para exibir suas cartas reais.
        </p>}
      </section>
      <RankPanel sha={sha}/>
    </div>
    <section className="panel rounded-xl p-4" aria-label="Dicas de fusões">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold text-gold">Dicas de fusões</h2>
          <p className="text-xs text-muted">Combinações das cartas que estão na sua mão</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={()=>setMode("pairs")}
            className={mode==="pairs"?"btn-gold":"btn-ghost"}>Duplas</button>
          <button type="button" onClick={()=>setMode("chains")}
            className={mode==="chains"?"btn-gold":"btn-ghost"}>Cadeias (2–5)</button>
        </div>
      </div>
      <div className="mt-3">
        {!hand?.ready?<Empty>As sugestões aparecerão quando o ePSXe identificar sua mão.</Empty>:
          visibleCombinations.length===0?<Empty>Nenhuma fusão identificada para estas cartas.</Empty>:
          mode==="pairs"?<div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {hand.pairs.slice(0,showAll?undefined:6).map((item,i)=>
              <div key={i} className="rounded-lg border border-line/60 bg-background/40 p-3">
                <p className="text-xs text-primary">Posições {item.slot_a} + {item.slot_b}</p>
                <p className="mt-1 font-semibold text-white">{item.result_name} #{item.result}</p>
                <MonsterStats card={cardsById.get(item.result)??null} className="mt-1"/>
              </div>)}
          </div>:<div className="grid gap-2 md:grid-cols-2">
            {hand.chains.slice(0,showAll?undefined:6).map((item,i)=>
              <div key={i} className="rounded-lg border border-gold/20 bg-background/40 p-3">
                <p className="font-semibold text-gold">{item.result_name} #{item.result}</p>
                <MonsterStats card={cardsById.get(item.result)??null} className="mt-1"/>
                <p className="mt-1 text-xs text-primary">Ordem: {item.slot_order.join(" → ")}</p>
                <ol className="mt-2 space-y-1 text-xs text-muted">{item.steps.map((step,j)=>
                  <li key={j}>{j+1}. #{step.material_a} + #{step.material_b} = #{step.result}</li>)}
                </ol>
              </div>)}
          </div>}
      </div>
      {hand?.ready&&combinations.length>6&&<button type="button"
        className="btn-ghost mt-3" onClick={()=>setShowAll(v=>!v)}>
        {showAll?"Mostrar menos":`Ver todas as ${combinations.length} combinações`}
      </button>}
      {hand?.ready&&mode==="chains"&&hand.chainsComplete===false&&
        <p className="mt-2 text-xs text-gold">Busca parcial: limite de combinações atingido.</p>}
    </section>
  </div>
}

function CardMatchPanel({mods,activeSha}:{mods:LocalMod[];activeSha:string|null}) {
  const [fromSha,setFromSha]=useState("")
  const [toSha,setToSha]=useState("")
  const [search,setSearch]=useState("")
  const [confidence,setConfidence]=useState("todas")
  const [result,setResult]=useState<CardMatchResult|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [aiBusy,setAiBusy]=useState(false)
  const [aiError,setAiError]=useState<string|null>(null)
  const [aiReview,setAiReview]=useState<CardAIMatchReport|null>(null)
  useEffect(()=>{
    const valid=new Set(mods.map(m=>m.sha256))
    setFromSha(old=>valid.has(old)?old:activeSha&&valid.has(activeSha)?activeSha:mods[0]?.sha256??"")
    setToSha(old=>valid.has(old)?old:mods.find(m=>m.sha256!==activeSha)?.sha256??mods[1]?.sha256??"")
  },[mods,activeSha])
  const compare=async(offset=0)=>{
    const api=desktopApi()
    if(!api||!fromSha||!toSha||fromSha===toSha)return
    setBusy(true)
    setError(null)
    setAiReview(null)
    setAiError(null)
    try{
      const data=await api.compare_mod_cards(fromSha,toSha,search,offset,30,confidence)
      setResult(data)
    }catch(e){
      setResult(null)
      setError(e instanceof Error?e.message:"Não foi possível comparar os catálogos locais.")
    }finally{setBusy(false)}
  }
  const review=async()=>{
    const api=desktopApi()
    if(!api||!result)return
    setAiBusy(true);setAiError(null);setAiReview(null)
    try{setAiReview(await api.review_card_matches(result.sourceSha,result.targetSha))}
    catch(e){setAiError(e instanceof Error?e.message:"Ollama não respondeu.")}
    finally{setAiBusy(false)}
  }
  return <section className="panel mt-4 rounded-xl p-4" aria-label="Identificador Universal de Cartas">
    <div className="mb-3">
      <h2 className="font-display text-xl font-semibold text-gold">Identificador Universal de Cartas</h2>
      <p className="mt-1 text-sm text-muted">
        Compare dois mods importados: nomes e imagens extraídas do SLUS/WA_MRG,
        atributos e IDs. Nenhuma correspondência altera automaticamente cartas, drops ou fusões.
      </p>
    </div>
    {mods.length<2?<Empty>Importe ao menos duas ISOs/BIN para comparar as cartas entre mods.</Empty>:<>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-muted">
          ISO de origem
          <select className="field rounded-md px-3 py-2 text-sm" value={fromSha}
            onChange={e=>{setFromSha(e.target.value);setResult(null)}}>
            <option value="">Selecione uma ISO</option>
            {mods.map(m=><option key={m.sha256} value={m.sha256}>{m.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          ISO de destino
          <select className="field rounded-md px-3 py-2 text-sm" value={toSha}
            onChange={e=>{setToSha(e.target.value);setResult(null)}}>
            <option value="">Selecione outra ISO</option>
            {mods.filter(m=>m.sha256!==fromSha).map(m=>
              <option key={m.sha256} value={m.sha256}>{m.name}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-muted">
          Buscar por nome ou ID
          <input className="field rounded-md px-3 py-2 text-sm" value={search}
            maxLength={100} placeholder="Ex.: Flower Wolf"
            onChange={e=>{setSearch(e.target.value);setResult(null)}}/>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          Confiança
          <select className="field rounded-md px-3 py-2 text-sm" value={confidence}
            onChange={e=>{setConfidence(e.target.value);setResult(null)}}>
            <option value="todas">Todas</option>
            <option value="alta">Candidatas fortes</option>
            <option value="revisar">Revisão necessária</option>
            <option value="sem_correspondencia">Sem correspondência</option>
          </select>
        </label>
        <button type="button" className="btn-gold disabled:opacity-40"
          disabled={busy||!fromSha||!toSha||fromSha===toSha||!desktopApi()}
          onClick={()=>void compare(0)}>
          {busy?"Comparando…":"Comparar cartas"}
        </button>
      </div>
      {error&&<p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
      {result&&<>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {([
            ["Candidatas fortes",result.summary.alta],
            ["Revisar",result.summary.revisar],
            ["Sem correspondência",result.summary.sem_correspondencia],
            ["IDs diferentes",result.summary.reordered],
          ] as const).map(([label,n])=><div key={label}
            className="rounded-lg border border-line/60 bg-background/50 p-3">
            <p className="font-display text-xl font-semibold text-primary tabular-nums">{n}</p>
            <p className="text-xs text-muted">{label}</p>
          </div>)}
        </div>
        {result.summary.revisar>0&&<div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" className="btn-ghost disabled:opacity-40"
            disabled={aiBusy||busy||!desktopApi()} onClick={()=>void review()}>
            {aiBusy?"Ollama analisando…":"Revisar dúvidas com Ollama (opcional)"}
          </button>
          <span className="text-xs text-muted">
            A IA revisa somente nomes e sinais já extraídos; não interpreta arquivos binários.
          </span>
        </div>}
        {aiError&&<p className="mt-2 text-sm text-gold" role="alert">{aiError}</p>}
        {aiReview&&<div className="mt-3 rounded-lg border border-gold/30 bg-background/50 p-3">
          <p className="text-sm font-semibold text-gold">Revisão do Ollama · hipótese, não confirmação</p>
          <p className="mt-1 text-xs text-muted">{aiReview.note}</p>
          <div className="mt-2 space-y-2">
            {aiReview.revisoes.map(item=><p key={item.sourceId+"-"+item.targetId}
              className="text-xs text-white">
              #{item.sourceId} → #{item.targetId}: {item.assessment.replaceAll("_"," ")}
              {item.reason?" · "+item.reason:""}
            </p>)}
            {aiReview.revisoes.length===0&&<p className="text-xs text-muted">
              Nenhum parecer específico. As candidatas permanecem sem validação.
            </p>}
          </div>
        </div>}
        <p className="mt-2 text-xs text-muted">
          Artes locais comparadas: {result.summary.sourceArtCount} na origem e {result.summary.targetArtCount} no destino.
          Os nomes vêm dos perfis SLUS. Mesmo as candidatas fortes não foram verificadas dentro do jogo.
        </p>
        <div className="mt-3 space-y-2">
          {result.rows.map(row=><div key={row.sourceId}
            className="grid gap-2 rounded-lg border border-line/50 bg-background/40 p-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-center">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-white">
                <span className="text-primary">#{row.sourceId}</span> {row.sourceName}
              </p>
              <p className="text-xs text-muted">Origem</p>
            </div>
            <span aria-hidden className="hidden text-primary md:inline">→</span>
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-white">
                {row.targetId===null?"Nenhuma candidata":
                  <><span className="text-primary">#{row.targetId}</span> {row.targetName}</>}
              </p>
              <p className="text-xs text-muted">
                {row.confidence==="alta"?"Candidata forte":
                  row.confidence==="revisar"?"Revisar correspondência":
                  "Não encontrada"}
                {row.ambiguous?" · existem alternativas":""}
              </p>
              {row.signals.length>0&&<p className="mt-1 text-xs text-gold">
                {row.signals.join(" · ").replaceAll("_"," ")}
              </p>}
            </div>
          </div>)}
          {result.rows.length===0&&<Empty>Nenhuma carta encontrada neste filtro.</Empty>}
        </div>
        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted">
          <span>{result.total?result.offset+1:0}–{Math.min(result.total,result.offset+result.rows.length)} de {result.total}</span>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost disabled:opacity-40"
              disabled={busy||result.offset===0}
              onClick={()=>void compare(Math.max(0,result.offset-30))}>Anterior</button>
            <button type="button" className="btn-ghost disabled:opacity-40"
              disabled={busy||result.offset+30>=result.total}
              onClick={()=>void compare(result.offset+30)}>Próxima</button>
          </div>
        </div>
        <p className="mt-3 text-xs text-gold">
          Comparação somente leitura. Confirme as candidatas ambíguas antes de
          transferir qualquer referência de outro mod.
        </p>
      </>}
    </>}
  </section>
}

function Mods({mods,sha,onRefresh,configured}:{
  mods:LocalMod[];sha:string|null;onRefresh:()=>Promise<void>;configured:boolean
}) {
  const [expandedSha,setExpandedSha]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState<string|null>(null)

  // A análise detalhada permanece disponível no motor, não nesta tela pública.
  const run=async(action:()=>Promise<unknown>,success:string)=>{
    setBusy(true);setMessage(null)
    try{
      await action()
      await onRefresh()
      setMessage(success)
    }catch{
      setMessage("Não foi possível concluir a operação. Confira o arquivo e tente novamente.")
    }finally{setBusy(false)}
  }
  const rescan=async(mod:LocalMod)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true);setMessage(null)
    try{
      await api.scan_sources(mod.sha256)
      await onRefresh()
      setMessage("Dados do mod atualizados.")
    }catch{
      setMessage("Não foi possível atualizar este mod. Verifique a ISO e tente novamente.")
    }finally{setBusy(false)}
  }
  return <>
    <Heading title="Biblioteca de Mods" subtitle="Seus jogos organizados em um só lugar"/>
    <section className="panel rounded-xl p-4">
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-gold disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.import_iso(),"Biblioteca atualizada.")}>
          <FilePlus2 className="size-4"/> Adicionar mod</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.configure_epsxe(),"Emulador configurado.")}>
          <Gamepad2 className="size-4"/> {configured?"Alterar emulador":"Configurar ePSXe"}</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!configured||!sha||!desktopApi()}
          onClick={()=>void run(()=>desktopApi()!.start_game(),"Jogo iniciado.")}>
          <Play className="size-4"/> Jogar</button>
        <button type="button" className="btn-ghost disabled:opacity-40" disabled={busy||!desktopApi()}
          onClick={()=>void onRefresh()}>
          <RefreshCcw className="size-4"/> Atualizar lista</button>
      </div>
      {message&&<p className="mt-3 text-sm text-gold" role="status">{message}</p>}
      <div className="mt-4 space-y-2">
        {mods.map(mod=>{
          const active=sha===mod.sha256
          const open=expandedSha===mod.sha256
          const details=[
            ["Cartas",mod.cards],
            ["Fusões",mod.fusions],
            ["Oponentes",mod.opponents??0],
            ["Drops",mod.dropEntries??0],
          ] as const
          return <article key={mod.sha256} className={
            "overflow-hidden rounded-xl border bg-panel-strong/70 transition-colors "+
            (active?"border-primary/65":"border-line/70 hover:border-primary/45")
          }>
            <button type="button" aria-expanded={open}
              aria-controls={"mod-info-"+mod.sha256.slice(0,16)}
              onClick={()=>setExpandedSha(open?null:mod.sha256)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-primary/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line/60 bg-background/80">
                <Gamepad2 className="size-5 text-primary"/>
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold text-white">{mod.name}</span>
                <span className="mt-0.5 block text-xs text-muted">
                  {active?"Pronto para jogar":mod.requiresReview?"Compatibilidade limitada":"Disponível"}
                </span>
              </span>
              {active&&<span className="rounded-md bg-primary/15 px-2 py-1 text-xs font-semibold text-primary">Ativo</span>}
              <ChevronDown className={"size-5 shrink-0 text-primary transition-transform duration-200 "+(open?"rotate-180":"")}/>
            </button>
            {open&&<div id={"mod-info-"+mod.sha256.slice(0,16)}
              className="border-t border-line/60 px-4 pb-4 pt-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {details.map(([label,value])=>
                  <div key={label} className="rounded-lg border border-line/40 bg-background/50 px-3 py-2 text-center">
                    <p className="font-display text-lg font-bold text-primary">{value>0?value.toLocaleString("pt-BR"):"—"}</p>
                    <p className="text-xs text-muted">{label}</p>
                  </div>)}
              </div>
              {mod.requiresReview&&<p className="mt-3 text-xs text-muted">
                Alguns recursos deste mod podem não estar disponíveis.
              </p>}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" disabled={busy||!desktopApi()||active}
                  className="btn-gold flex-1 disabled:opacity-40" onClick={()=>{
                    const ok=!mod.requiresReview||window.confirm("Este mod tem compatibilidade parcial. Ativar os recursos disponíveis?")
                    if(ok)void run(()=>desktopApi()!.activate_mod(mod.sha256,mod.requiresReview),"Mod ativado.")
                  }}>{active?"Mod ativo":"Ativar mod"}</button>
                <button type="button" className="btn-ghost flex-1 disabled:opacity-40"
                  disabled={busy||!desktopApi()} onClick={()=>void rescan(mod)}>
                  <RefreshCcw className="size-4"/> Atualizar dados
                </button>
              </div>
            </div>}
          </article>
        })}
      </div>
      {!mods.length&&<Empty>Nenhum mod adicionado. Importe uma ISO/BIN para começar.</Empty>}
    </section>
  </>
}

function CardDropSourcesPanel({sha,card}:{sha:string|null;card:LocalCard}) {
  const [result,setResult]=useState<CardDropSources|null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState<string|null>(null)

  useEffect(()=>{
    let mounted=true
    setResult(null)
    setError(null)
    const api=desktopApi()
    if(!api||!sha){setLoading(false);return()=>{mounted=false}}
    setLoading(true)
    void api.get_card_drop_sources(card.id).then(data=>{
      if(mounted)setResult(data)
    }).catch(e=>{
      if(mounted)setError(e instanceof Error?e.message:"Consulta de drops indisponível.")
    }).finally(()=>{if(mounted)setLoading(false)})
    return()=>{mounted=false}
  },[sha,card.id])

  const verifiedResponse=result?.romSha===sha && result.cardId===card.id
  const rows=verifiedResponse&&result.available?result.rows:[]
  return <section className="mt-4 rounded-lg border border-line/70 bg-background/60 p-3" aria-label="Onde conseguir esta carta">
    <h3 className="mb-2 font-semibold text-gold">Onde conseguir esta carta</h3>
    {loading?<p className="text-sm text-muted" role="status">Consultando drops da ISO ativa…</p>:
      error?<p className="text-sm text-danger" role="alert">{error}</p>:
      !verifiedResponse?<p className="text-sm text-muted">Aguardando dados da ISO ativa.</p>:
      !result.available?<p className="text-sm text-muted">Drops ainda não identificados neste mod. {result.status}</p>:
      rows.length===0?<p className="text-sm text-muted">Nenhum oponente confirmado para esta carta.</p>:
      <div className="space-y-2">
        <p className="text-xs text-primary">{result.total} possibilidade(s), ordenadas por chance de drop.</p>
        {!result.rankLabelsVerified&&<p className="text-xs text-gold">
          RANKs agrupados segundo o padrão original; confira o mapeamento em duelo neste mod.
        </p>}
        <ul className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
          {rows.map(row=><li key={row.opponentId+"-"+row.group}
            className="flex items-start justify-between gap-2 rounded-md border border-line/50 bg-panel-strong/50 p-2">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-white">#{row.opponentId} {row.opponentName}</p>
              <p className="text-xs text-muted">{row.eligibleRanks.join(" / ")} · {row.groupLabel}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-sm font-semibold tabular-nums text-primary">
                {row.chancePercent.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:4})}%
              </p>
              <p className="text-[11px] text-muted">{row.weight}/2048</p>
            </div>
          </li>)}
        </ul>
        <p className="text-[11px] text-muted">Fonte: {result.source}. Pesos extraídos da ISO ativa; não são garantia de obtenção.</p>
      </div>}
  </section>
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
            </div>
            <CardDropSourcesPanel key={(sha??"sem-iso")+"-"+chosen.id} sha={sha} card={chosen}/></>:<Empty>Selecione uma carta.</Empty>}
        </aside>
      </div>
    </section>
  </>
}

function FusionIllustration({id,name,sha,card,role,onPreview}:{
  id:number;name:string;sha:string|null;card:LocalCard|null;role:string;
  onPreview:(preview:CardPreviewSelection|null)=>void
}) {
  const displayed:LocalCard=card??{
    id,name,type:"",attribute:"",category:"Não identificada",
    atk:null,def:null,effect:null,effectSource:null
  }
  return <div className="flex min-w-0 flex-col items-center gap-1.5">
    <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{role}</span>
    <button type="button" aria-label={`Ver detalhes e drops de ${name}`}
      onMouseEnter={event=>onPreview({card:displayed,anchor:event.currentTarget})}
      onMouseLeave={()=>onPreview(null)}
      onFocus={event=>onPreview({card:displayed,anchor:event.currentTarget})}
      onBlur={()=>onPreview(null)}
      className="group flex min-w-0 w-full flex-col items-center gap-1.5 rounded-md p-1 transition-all duration-200 hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
      <div className="w-16 origin-center transition-transform duration-200 group-hover:scale-105 group-focus-visible:scale-105 sm:w-20">
        <CardThumbnail key={String(sha)+"-"+id} card={displayed} sha={sha}/>
      </div>
      <span className="text-center text-[11px] font-semibold text-gold">#{id}</span>
      <span className="line-clamp-2 min-h-8 break-words text-center text-xs font-medium text-foreground">{name}</span>
      <MonsterStats card={displayed} className="text-center text-[10px]"/>
    </button>
  </div>
}


function Fusions({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const [query,setQuery]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"def"|"type"|"name">("id")
  const [cardType,setCardType]=useState("")
  const [offset,setOffset]=useState(0)
  const [records,setRecords]=useState<FusionPage|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const types=useMemo(()=>Array.from(new Set(cards.map(c=>c.type||c.category).filter(Boolean))).sort((a,b)=>a.localeCompare(b,"pt-BR")),[cards])
  useEffect(()=>{setQuery("");setSort("id");setCardType("");setOffset(0);setRecords(null)},[sha])
  useEffect(()=>{setPreview(null)},[sha,query,offset,sort,cardType])
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
          className="relative rounded-xl border border-line/80 bg-gradient-to-br from-panel-strong/90 via-[#0b1a35] to-background p-3 shadow-[inset_0_1px_0_rgb(245_184_61/0.09)] transition-colors hover:border-primary/60">
          <div className="grid grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)] items-start gap-1">
            <FusionIllustration id={r.a} name={r.nameA} card={cardsById.get(r.a)??null} sha={sha} role="Material A" onPreview={setPreview}/>
            <span className="pt-14 text-center font-display text-xl font-bold text-primary" aria-hidden>+</span>
            <FusionIllustration id={r.b} name={r.nameB} card={cardsById.get(r.b)??null} sha={sha} role="Material B" onPreview={setPreview}/>
            <span className="pt-14 text-center font-display text-xl font-bold text-gold" aria-hidden>→</span>
            <FusionIllustration id={r.result} name={r.nameResult} card={cardsById.get(r.result)??null} sha={sha} role="Resultado" onPreview={setPreview}/>
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
      <CardHoverPreview selection={preview} sha={sha} onClose={()=>setPreview(null)}/>
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
    {page==="drops"&&<DropsPage sha={state?.activeSha??null} cards={state?.cards??[]}/>}
  </div>
}
