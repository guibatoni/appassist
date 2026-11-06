"use client"

import Image from "next/image"
import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, ClipboardCopy, FilePlus2, Gamepad2,
  GitMerge, Layers, Play, RefreshCcw, Search, Shield, Swords, Upload,
} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi, useDesktopState} from "@/lib/desktop"
import {DropsPage} from "./drops-page"
import {copyOpponentReport} from "@/lib/opponent-report"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"
import type {LocalCard, HandState, FusionPage, LocalMod, RankState, CardMatchResult, CardAIMatchReport, ModScanDiagnostic, CardDropSources, WindowObservationResult, CandidateMatrixPage, LiveOpponentProbe, LiveDiagnosticsStatus, PrivateEvidenceSyncStatus, IsoLayoutComparison} from "@/lib/desktop"

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

function LiveOpponentPanel() {
  const [sample,setSample]=useState<LiveOpponentProbe|null>(null)
  useEffect(()=>{
    let active=true
    let fetching=false
    const read=async()=>{
      if(fetching)return
      const api=desktopApi()
      if(!api)return
      fetching=true
      try{
        const next=await api.get_live_opponent()
        if(active)setSample(next)
      }catch{
        if(active)setSample(null)
      }finally{fetching=false}
    }
    void read()
    const timer=window.setInterval(()=>void read(),2500)
    return ()=>{active=false;window.clearInterval(timer)}
  },[])
  return <section className="mt-3 rounded-lg border border-primary/40 bg-background/30 px-3 py-3">
    <p className="text-sm font-semibold text-primary">
      Leitura automática do adversário no emulador (experimental)
    </p>
    {sample?.ready&&Number.isInteger(sample.runtimeOpponentId)?
      <p className="mt-2 text-xs text-muted">
        ID de adversário candidato na RAM PS1:{" "}
        <strong className="text-primary">#{sample.runtimeOpponentId}</strong>.
        {" "}LP lidos: {sample.playerLP} / {sample.opponentLP}.
        {" "}{sample.validationMethod==="known_hand_anchor"
          ?"Mapeamento cruzado com as cinco cartas da mão já lidas pelo DUELTRACE."
          :"Mapeamento cruzado com estruturas históricas do jogo original."}
        {" "}O ID ainda não foi relacionado ao nome da ISO nem ao bloco de drops.
        {(sample.localRuntimeIdEvents??0)>0?
          ` ${sample.localRuntimeIdEvents} mudança(s) de ID registrada(s) automaticamente
          nesta sessão iniciada pelo DUELTRACE (evidência provisória).`:""}
      </p>:
      <p className="mt-2 text-xs text-muted">
        {sample?.status==="no_epsxe"?"ePSXe não encontrado. A leitura começa automaticamente quando houver um duelo.":
         sample?.status==="multiple_epsxe_processes"?"Mais de um processo ePSXe detectado; não é seguro escolher um.":
         sample?.status==="ram_mapping_not_validated"?"O ePSXe foi encontrado e o duelo está em análise, mas nenhum mapeamento de RAM passou nas verificações. Isso não significa que você precisa iniciar outro duelo.":
         "Buscando adversário no ePSXe sem alterar a memória do jogo."}
      </p>}
    {sample?.status==="ram_mapping_not_validated"&&
      <div className="mt-2 rounded-md border border-line/60 p-2 text-xs text-muted">
        <p>Diagnóstico de RAM: {sample.memoryRegionsExamined??0} regiões consultadas;
          {" "}{sample.readableLargeRegions??0} regiões grandes legíveis;
          {" "}{sample.candidateBasesExamined??0} bases examinadas.
          {sample.searchedHighMemory?" Busca em memória alta do Windows habilitada.":""}
        </p>
        <p className="mt-1">
          Candidatos rejeitados:{" "}
          {sample.validationBreakdown?.unreadableFields??0} por dados não legíveis;
          {" "}{sample.validationBreakdown?.opponentIdOutOfRange??0} por ID fora da faixa;
          {" "}{sample.validationBreakdown?.implausibleLifePoints??0} por LP;
          {" "}{sample.validationBreakdown?.implausibleHandIndices??0} por índices da mão;
          {" "}{sample.validationBreakdown?.implausibleDrawHistory??0} por histórico;
          {" "}{sample.validationBreakdown?.unstableSamples??0} por instabilidade.
        </p>
        <p className="mt-1 text-gold">
          O painel não expõe endereços, conteúdo da RAM ou outros processos.
          Nenhum ID foi confirmado e não é necessário registrar outro duelo.
        </p>
      </div>}
    <p className="mt-1 text-xs text-gold">
      O endereço do ID é conhecido no jogo original, mas o GOG MOD 2.2 pode
      usar outra estrutura. A leitura é somente observacional e não ativa drops.
    </p>
  </section>
}

function LiveDiagnosticsPanel({sha}:{sha:string|null}) {
  const [status,setStatus]=useState<LiveDiagnosticsStatus|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [report,setReport]=useState("")
  const [message,setMessage]=useState("")
  const [sync,setSync]=useState<PrivateEvidenceSyncStatus|null>(null)
  const [syncRepo,setSyncRepo]=useState("")
  const [syncToken,setSyncToken]=useState("")
  const [syncConsent,setSyncConsent]=useState(false)

  useEffect(()=>{
    let active=true
    let querying=false
    const refresh=async()=>{
      const api=desktopApi()
      if(!api||querying)return
      querying=true
      try{
        const [next,nextSync]=await Promise.all([
          api.get_live_diagnostics_status(),
          api.get_private_evidence_sync_status(),
        ])
        if(active){setStatus(next);setSync(nextSync)}
      }catch{
        if(active)setStatus(null)
      }finally{querying=false}
    }
    void refresh()
    const interval=window.setInterval(()=>void refresh(),3000)
    return ()=>{active=false;window.clearInterval(interval)}
  },[sha])

  const toggle=async()=>{
    const api=desktopApi()
    if(!api||busy||!sha)return
    setError(null);setBusy(true);setReport("");setMessage("")
    try {
      const next=status?.running
        ? await api.stop_live_diagnostics()
        : await api.start_live_diagnostics()
      setStatus(next)
    }catch(e){
      setError(e instanceof Error?e.message:"Falha ao controlar o diagnóstico.")
    }finally{setBusy(false)}
  }

  const connectPrivate=async()=>{
    const api=desktopApi()
    if(!api||busy||!syncConsent)return
    setBusy(true);setError(null);setMessage("")
    try {
      const next=await api.configure_private_evidence_sync(
        syncRepo.trim(),syncToken,true)
      setSync(next);setSyncToken("");setSyncConsent(false)
      setMessage("Sincronização privada ativada. A coleta começa quando você iniciar o diagnóstico.")
    }catch(e){
      setError(e instanceof Error?e.message:"Falha na autenticação privada.")
    }finally{setBusy(false)}
  }
  const disconnectPrivate=async()=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true);setError(null);setMessage("")
    try{
      setSync(await api.disable_private_evidence_sync())
      setSyncToken("");setSyncConsent(false)
      setMessage("Envios desativados e credencial local apagada. Relatórios já enviados permanecem no GitHub.")
    }catch(e){
      setError(e instanceof Error?e.message:"Falha ao desativar sincronização.")
    }finally{setBusy(false)}
  }

  const copyReport=async()=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true);setError(null);setMessage("")
    try{
      const text=await api.export_live_diagnostics()
      setReport(text)
      try{
        await navigator.clipboard.writeText(text)
        setMessage("Relatório copiado. Cole-o nesta conversa para análise.")
      }catch{
        setMessage("O relatório está no campo abaixo. Selecione e copie para enviar.")
      }
    }catch(e){setError(e instanceof Error?e.message:"Falha ao preparar relatório.")}
    finally{setBusy(false)}
  }

  return <section className="panel rounded-xl border-primary/40 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 className="font-display text-lg font-semibold text-primary">
          DUELTRACE Live Diagnostics
        </h2>
        <p className="mt-1 text-xs text-muted">
          Monitor local e opcional: registra mudanças na mão, falhas da RAM,
          identificador candidato do adversário e projeções já observadas de RANK.
        </p>
      </div>
      <span className={"text-xs "+(status?.running?"text-success":"text-muted")}>
        {status?.running?"● Capturando localmente":"○ Desligado"}
      </span>
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <button className={status?.running?"btn-ghost":"btn-gold"}
        type="button" onClick={()=>void toggle()}
        disabled={busy||!sha||!desktopApi()}>
        {status?.running?"Parar diagnóstico":"Iniciar diagnóstico"}
      </button>
      <button className="btn-ghost" type="button" onClick={()=>void copyReport()}
        disabled={busy||!status?.readyToCopy}>
        Copiar relatório para o ChatGPT
      </button>
    </div>
    <p className="mt-2 text-xs text-muted">
      Amostras: {status?.sampleCount??0} · Mudanças relevantes: {status?.changeCount??0}
      {" "}· Última leitura: {status?.lastObservedAtUTC?
        new Date(status.lastObservedAtUTC).toLocaleTimeString("pt-BR"):"—"}
    </p>
    {status?.forensicReview?.candidateStableDespiteHandAndLpFieldChanges&&
      <p role="status" className="mt-2 text-xs text-gold">
        Evidência provisória: o byte candidato {status.forensicReview.candidateIds.join(", ")}
        {" "}permaneceu constante em {status.forensicReview.candidateObservedInEvents}
        {" "}eventos, apesar de {status.forensicReview.distinctHands} mãos diferentes e
        {" "}{status.forensicReview.distinctLegacyLpPairs} pares de campos de LP legados.
        Esses campos podem ter outro significado no mod. Sem confirmação independente
        do adversário, não é possível ativar drops nem identificar oponentes.
      </p>}
    <p className="mt-1 text-xs text-gold">
      Sem sincronização privada ativa, o relatório permanece somente no PC.
      Nenhuma conexão direta com esta conversa é estabelecida. IDs e RANKs
      continuam provisórios, mesmo após um envio.
    </p>
    <div className="mt-4 rounded-lg border border-line/70 p-3">
      <h3 className="text-sm font-semibold text-primary">Sincronização privada de evidências</h3>
      <p className="mt-1 text-xs text-muted">
        Opcional, via HTTPS para um repositório GitHub privado separado. Com a coleta
        ativa, envia o JSON sanitizado a cada ~60 segundos e ao encerrar.
        Não envia ISO, arte, RAM bruta, caminhos do PC nem token.
        O ChatGPT não acompanha o PC continuamente; os relatórios poderão ser
        consultados pelo GitHub conectado quando você solicitar análise.
      </p>
      {sync?.enabled?
        <div className="mt-3 space-y-2">
          <p className="text-xs text-success">● Envio autorizado para {sync.repository}</p>
          <p className="text-xs text-muted">Último envio: {sync.lastSyncedAtUTC?
            new Date(sync.lastSyncedAtUTC).toLocaleString("pt-BR"):"Ainda não realizado"}</p>
          {sync.lastError&&<p role="alert" className="text-xs text-danger">{sync.lastError}</p>}
          <button type="button" className="btn-ghost" disabled={busy}
            onClick={()=>void disconnectPrivate()}>Desativar e apagar credencial local</button>
        </div>:
        <div className="mt-3 space-y-2">
          <label className="block text-xs text-muted" htmlFor="sync-repo">
            Repositório privado (usuario/nome-do-repositorio)
          </label>
          <input id="sync-repo" className="field w-full p-2 text-xs"
            autoComplete="off" value={syncRepo}
            onChange={e=>setSyncRepo(e.target.value)} placeholder="usuario/dueltrace-evidencias"/>
          <label className="block text-xs text-muted" htmlFor="sync-token">
            Token de acesso fino do GitHub (Contents: Read and write, somente esse repositório)
          </label>
          <input id="sync-token" type="password" className="field w-full p-2 text-xs"
            autoComplete="off" spellCheck={false} value={syncToken}
            onChange={e=>setSyncToken(e.target.value)} placeholder="Cole o token somente aqui"/>
          <label className="flex items-start gap-2 text-xs text-muted">
            <input type="checkbox" checked={syncConsent}
              onChange={e=>setSyncConsent(e.target.checked)}/>
            Autorizo o envio periódico dos relatórios sanitizados para esse repositório
            privado. Sei que os arquivos enviados continuam lá após desativar.
          </label>
          <button type="button" className="btn-gold" disabled={busy||!syncRepo.trim()||
            !syncToken.trim()||!syncConsent} onClick={()=>void connectPrivate()}>
            Verificar privacidade e ativar
          </button>
          <p className="text-xs text-gold">
            Não coloque o token nesta conversa nem no repositório de código do DUELTRACE.
            A credencial fica criptografada para seu usuário Windows.
          </p>
        </div>}
    </div>
    {error&&<p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
    {message&&<p role="status" className="mt-2 text-xs text-primary">{message}</p>}
    {report&&<textarea readOnly value={report}
      aria-label="Relatório técnico sanitizado do DUELTRACE"
      className="field mt-2 max-h-44 w-full resize-y p-2 font-mono text-xs"
      rows={5} onFocus={e=>e.currentTarget.select()}/>}
  </section>
}

function StructuralMatrixExplorer({mod}:{mod:LocalMod}) {
  const [block,setBlock]=useState(-1)
  const [group,setGroup]=useState(1)
  const [query,setQuery]=useState("")
  const [debouncedQuery,setDebouncedQuery]=useState("")
  const [offset,setOffset]=useState(0)
  const [result,setResult]=useState<CandidateMatrixPage|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)

  useEffect(()=>{
    const id=window.setTimeout(()=>setDebouncedQuery(query),350)
    return ()=>window.clearTimeout(id)
  },[query])

  useEffect(()=>{
    let active=true
    const api=desktopApi()
    if(!api)return
    setBusy(true);setError(null)
    void api.get_candidate_matrix(mod.sha256,block,group,debouncedQuery,offset,15).then(
      next=>{if(active){setResult(next);setBusy(false)}},
      reason=>{if(active){setError(reason instanceof Error?reason.message:"Matriz indisponível.");setBusy(false)}},
    )
    return ()=>{active=false}
  },[mod.sha256,block,group,debouncedQuery,offset])

  const chooseBlock=(value:number)=>{
    setBlock(value);setOffset(0)
  }
  return <section className="mt-3 rounded-lg border border-primary/30 bg-background/40 px-3 py-3">
    <p className="text-sm font-semibold text-primary">
      Dados automáticos da ISO — matrizes candidatas
    </p>
    <p className="mt-1 text-xs text-gold">
      O DUELTRACE lê as distribuições diretamente da ISO. São pesos estruturais
      reais, mas a identidade do adversário e os grupos de RANK ainda não foram
      confirmados. Esta área NÃO representa drops oficiais.
    </p>
    <div className="mt-3 grid gap-2 sm:grid-cols-3">
      <label className="flex flex-col gap-1 text-xs text-muted">
        Bloco físico (não é ID do adversário)
        <select className="field rounded-md px-2 py-2 text-sm"
          value={block} onChange={e=>chooseBlock(Number(e.target.value))}>
          <option value={-1}>Automático (hipótese disponível)</option>
          {Array.from({length:Math.min(result?.blockCount??mod.modFamilyEvidence?.consecutiveBlocks??0,128)},(_,i)=>
            <option key={i} value={i}>Bloco físico {i}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Tabela estrutural
        <select className="field rounded-md px-2 py-2 text-sm" value={group}
          onChange={e=>{setGroup(Number(e.target.value));setOffset(0)}}>
          <option value={0}>Deck candidato (grupo 0)</option>
          <option value={1}>Distribuição candidata 1</option>
          <option value={2}>Distribuição candidata 2</option>
          <option value={3}>Distribuição candidata 3</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Buscar carta (ID ou nome)
        <input className="field rounded-md px-2 py-2 text-sm"
          maxLength={80} placeholder="ID ou nome da Biblioteca"
          value={query} onChange={e=>{setQuery(e.target.value);setOffset(0)}}/>
      </label>
    </div>
    {busy&&<p className="mt-2 text-xs text-muted">Lendo dados da ISO local...</p>}
    {error&&<p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
    {result&&!result.available&&!busy&&<p className="mt-2 text-xs text-gold">
      Este formato ainda não tem matrizes exploráveis verificadas estruturalmente
      ({result.status}). A Biblioteca de cartas continua disponível.
    </p>}
    {result?.available&&<div className="mt-3">
      <p className="text-xs text-muted">
        Bloco físico <strong>{result.physicalBlockIndex}</strong> de {result.blockCount} ·
        {" "}{result.nonzeroCards} cartas com peso · soma dos pesos: {result.totalWeight}.
        {" "}{result.selectionReason==="single_hypothesis_from_saved_observation"
          ?"Bloco sugerido automaticamente pelas observações locais (não confirmado)."
          :"Bloco exploratório sem ID de adversário confirmado."}
      </p>
      <div className="mt-2 max-h-72 overflow-auto rounded-md border border-line/60">
        <table className="w-full text-left text-xs text-muted">
          <thead className="sticky top-0 bg-panel-strong text-primary">
            <tr>
              <th className="px-2 py-2">Carta da ISO</th>
              <th className="px-2 py-2">ATK / DEF</th>
              <th className="px-2 py-2">Peso</th>
              <th className="px-2 py-2">%</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map(row=><tr key={row.id} className="border-t border-line/30">
              <td className="px-2 py-2">#{row.id} · {row.name}</td>
              <td className="px-2 py-2">{row.atk??"—"} / {row.def??"—"}</td>
              <td className="px-2 py-2">{row.weight}/2048</td>
              <td className="px-2 py-2">{row.chancePercent.toFixed(2)}%</td>
            </tr>)}
          </tbody>
        </table>
        {result.rows.length===0&&<p className="p-3 text-xs text-muted">
          Nenhuma carta corresponde ao filtro nesta distribuição.
        </p>}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted">
        <span>{result.total??0} cartas correspondentes ·
          {" "}proporções condicionais ao grupo não identificado</span>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost disabled:opacity-40"
            onClick={()=>setOffset(n=>Math.max(0,n-15))} disabled={busy||offset===0}>
            Anterior
          </button>
          <button type="button" className="btn-ghost disabled:opacity-40"
            onClick={()=>setOffset(n=>n+15)}
            disabled={busy||offset+15>=(result.total??0)}>Próxima</button>
        </div>
      </div>
    </div>}
  </section>
}

function WindowEvidenceForm({mod}:{mod:LocalMod}) {
  const opponentChoices=mod.structuralOpponentChoices??[]
  const [slot,setSlot]=useState("")
  const [rank,setRank]=useState("")
  const [reward,setReward]=useState("")
  const [played,setPlayed]=useState("")
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [summary,setSummary]=useState<WindowObservationResult|null>(null)

  useEffect(()=>{
    const api=desktopApi()
    if (!api)return
    let active=true
    void api.get_window_observations(mod.sha256).then(
      result=>{if(active)setSummary(result)},
      ()=>{if(active)setSummary(null)},
    )
    return ()=>{active=false}
  },[mod.sha256])

  const submit=async(event:React.FormEvent<HTMLFormElement>)=>{
    event.preventDefault()
    if(busy)return
    const api=desktopApi()
    if(!api){setError("Abra o aplicativo para Windows.");return}
    const id=Number(slot),card=Number(reward)
    const tokens=played.trim()?played.trim().split(/[\s,;]+/):[]
    const cards=tokens.map(Number)
    const upper=rank.trim().toUpperCase()
    if(!Number.isInteger(id)||!opponentChoices.some(o=>o.slot===id)||
       !Number.isInteger(card)||
       card<1||card>722||!/^[A-Z0-9_-]{1,24}$/.test(upper)||
       cards.length>24||cards.some(v=>!Number.isInteger(v)||v<1||v>722)||
       new Set(cards).size!==cards.length){
      setError("Verifique índice (1–39), carta recebida (1–722), RANK e IDs das cartas usadas (sem repetições).")
      return
    }
    setBusy(true);setError(null)
    try {
      const result=await api.record_window_observation(mod.sha256,id,upper,card,cards)
      setSummary(result)
      setReward("");setPlayed("")
    }catch(e){
      setError(e instanceof Error?e.message:"Falha ao gravar observação do duelo.")
    }finally{setBusy(false)}
  }
  const undoLast=async()=>{
    if(busy||!summary?.observationCount)return
    if(!window.confirm("Desfazer apenas a última observação? As demais serão preservadas e analisadas novamente."))return
    const api=desktopApi()
    if(!api){setError("Abra o aplicativo para Windows.");return}
    setBusy(true);setError(null)
    try{
      setSummary(await api.undo_last_window_observation(mod.sha256))
    }catch(e){
      setError(e instanceof Error?e.message:"Não foi possível desfazer o registro.")
    }finally{setBusy(false)}
  }
  const status=summary?.analysis?.status??"awaiting_independent_duels"
  const label:Record<string,string>={
    awaiting_independent_duels:"Aguardando observações.",
    single_window_suggested_not_verified:"Uma janela é compatível com os relatos, ainda sem comprovação em jogo.",
    multiple_windows_still_possible:"As duas janelas continuam possíveis.",
    observations_conflict_with_all_windows:"Nenhuma janela explica todos os registros sob a hipótese de que posição estrutural = ID de tabela. Verifique as observações abaixo; isso não invalida a ISO.",
    resource_ambiguous_or_missing:"Recurso ainda não identificado de forma única.",
  }
  return <details className="mt-3 rounded-lg border border-line/60 bg-background/30 px-3 py-3">
    <summary className="cursor-pointer text-sm font-semibold text-primary">
      Registrar evidência de duelo (experimental)
    </summary>
    <p className="mt-2 text-xs text-gold">
      Selecione o adversário pelo nome recuperado da ISO. A posição estrutural
      será preenchida automaticamente, mas não é um ID confirmado pelo jogo.
      Registre somente duelos observados: esses dados não liberam drops nem RANK.
    </p>
    <form onSubmit={e=>void submit(e)} className="mt-3 grid gap-2 md:grid-cols-2">
      <label className="flex flex-col gap-1 text-xs text-muted">
        Adversário extraído da ISO
        <select className="field rounded-md px-3 py-2 text-sm" value={slot}
          onChange={e=>setSlot(e.target.value)} required disabled={opponentChoices.length!==39}>
          <option value="">Selecione o nome do adversário...</option>
          {opponentChoices.map(o=><option key={o.slot} value={o.slot}>
            {o.name} (posição estrutural {o.slot})
          </option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        RANK exibido no fim do duelo
        <input className="field rounded-md px-3 py-2 text-sm" maxLength={24}
          placeholder="Ex.: S-POW" value={rank}
          onChange={e=>setRank(e.target.value)} required/>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        ID da carta recebida
        <input className="field rounded-md px-3 py-2 text-sm" type="number" min={1} max={722}
          value={reward} onChange={e=>setReward(e.target.value)} required/>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        IDs das cartas usadas pelo adversário (opcional)
        <input className="field rounded-md px-3 py-2 text-sm" maxLength={120}
          placeholder="Ex.: 12, 58, 210" value={played}
          onChange={e=>setPlayed(e.target.value)}/>
      </label>
      <div className="md:col-span-2 flex flex-wrap items-center gap-3">
        <button type="submit" disabled={busy||!desktopApi()||!slot||opponentChoices.length!==39} className="btn-ghost disabled:opacity-40">
          {busy?"Comparando...":"Salvar e comparar janelas"}
        </button>
        <span className="text-xs text-muted">
          {summary?.observationCount??0} observação(ões) locais · {label[status]??"Análise provisória disponível."}
        </span>
      </div>
      {opponentChoices.length!==39&&<p className="md:col-span-2 text-xs text-gold">
        Os 39 nomes ainda não estão disponíveis neste perfil. Clique em Atualizar dados
        antes de registrar o duelo. Não atribua posições manualmente.
      </p>}
      {error&&<p role="alert" className="md:col-span-2 text-xs text-danger">{error}</p>}
      {(summary?.analysis?.windowCount??0)>0&&<p className="md:col-span-2 text-xs text-muted">
        Janelas: {summary?.analysis?.windowCount} · Compatíveis sob hipótese:{" "}
        {summary?.analysis?.compatibleWindowCount??0}.
        {" "}Identidade do adversário e grupos de RANK não verificados.
      </p>}
      {(summary?.analysis?.windows?.length??0)>0&&<div className="md:col-span-2 mt-2 rounded-md border border-line/50 p-3">
        <p className="text-xs font-semibold text-primary">Motivos das incompatibilidades (hipóteses, não erros da ISO)</p>
        <ul className="mt-2 space-y-1 text-xs text-muted">
          {(summary?.analysis?.windows??[]).map(w=><li key={w.index}>
            Janela {w.index+1}: {w.deckContradictions} cartas vistas ausentes do deck candidato,
            {" "}{w.rewardContradictions} recompensas ausentes das três tabelas;
            {" "}{w.sameRankGroupConflicts} conflitos independentes entre grupos de um mesmo RANK.
            {(w.rankGroupNotAssessable??0)>0?
              " O grupo RANK não pode ser avaliado quando a recompensa está ausente.":""}
            {" "}{w.compatibleUnderHypothesis?"Compatível sob hipótese.":"Não explica todos os registros."}
          </li>)}
        </ul>
        <p className="mt-2 text-xs text-gold">
          As posições dos 39 nomes não foram comprovadas como IDs de jogo.
          Uma incompatibilidade pode indicar ordem diferente ou mapeamento de RANK desconhecido.
        </p>
      </div>}
      {(summary?.analysis?.unmappedPhysicalBlocks?.slots?.length??0)>0&&
        <div className="md:col-span-2 mt-2 rounded-md border border-line/50 p-3">
          <p className="text-xs font-semibold text-primary">
            Investigação de blocos físicos sem pressupor a ordem dos adversários
          </p>
          {(summary?.analysis?.unmappedPhysicalBlocks?.slots??[]).map(slot=>
            <p key={slot.structuralNamePosition} className="mt-2 text-xs text-muted">
              Posição estrutural {slot.structuralNamePosition}:{" "}
              {slot.physicalBlocksExamined} blocos examinados;{" "}
              {slot.possiblePhysicalBlocks} blocos conseguem explicar os registros,
              sob a hipótese de que as matrizes sejam decks/drops desta ISO.
              {slot.candidateSamples.length>0?
                ` Índices físicos candidatos (base zero): ${slot.candidateSamples.map(x=>x.physicalBlockIndex).join(", ")}.`:""}
            </p>)}
          <p className="mt-2 text-xs text-gold">
            Estes blocos são hipóteses de pesquisa: não demonstram qual adversário
            ou grupo RANK o jogo usa. Nenhum drop foi liberado.
          </p>
        </div>}
      {(summary?.entries?.length??0)>0&&<div className="md:col-span-2 mt-2 rounded-md border border-line/50 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold text-primary">
            Duelos registrados nesta ISO ({summary?.observationCount??0})
          </p>
          <button type="button" onClick={()=>void undoLast()}
            disabled={busy||!desktopApi()} className="btn-ghost text-xs disabled:opacity-40">
            Desfazer último registro
          </button>
        </div>
        <ol className="mt-2 space-y-1 text-xs text-muted">
          {(summary?.entries??[]).slice(-8).map(item=><li key={item.index}>
            #{item.index}: {opponentChoices.find(o=>o.slot===item.opponentSlot)?.name??
              `Posição estrutural ${item.opponentSlot}`} · {item.rank} ·
            carta recebida #{item.rewardCardId}
            {item.playedCardIds.length>0?
              ` · cartas vistas: ${item.playedCardIds.join(", ")}`:""}
          </li>)}
        </ol>
        {(summary?.observationCount??0)>8&&<p className="mt-1 text-xs text-muted">
          Exibindo os oito registros mais recentes.
        </p>}
      </div>}
    </form>
  </details>
}

function Mods({mods,sha,onRefresh,configured}:{
  mods:LocalMod[];sha:string|null;onRefresh:()=>Promise<void>;configured:boolean
}) {
  const [expandedSha,setExpandedSha]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState<string|null>(null)
  const [comparison,setComparison]=useState<IsoLayoutComparison|null>(null)

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
  const copyDiagnostics=async(mod:LocalMod)=>{
    setBusy(true);setMessage(null)
    try {
      const windows=await copyOpponentReport(mod)
      setMessage("Diagnóstico técnico copiado ("+windows+
        " janelas, somente contagens). Cole o texto na conversa para análise.")
    } catch(err) {
      setMessage(err instanceof Error ? err.message :
        "Não foi possível copiar o diagnóstico do mod.")
    } finally {setBusy(false)}
  }
  const compareIso=async(mod:LocalMod)=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true);setMessage(null)
    try{
      const result=await api.compare_mod_layouts(mod.sha256)
      setComparison(result)
      setMessage(result.comparedProfiles>0
        ?"Comparação estrutural concluída. Dados continuam provisórios."
        :"Nenhuma outra ISO com relatório comparável. Atualize dados dos demais mods.")
    }catch(err){
      setMessage(err instanceof Error?err.message:"Não foi possível comparar as ISOs.")
    }finally{setBusy(false)}
  }
  const rescan=async(mod:LocalMod)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true);setMessage(null)
    try{
      const result=await api.scan_sources(mod.sha256)
      await onRefresh()
      setMessage((result.cardCount??0)>0
        ?`${result.cardCount} cartas extraídas; ${result.opponentCount??0} adversários disponíveis.`
          +(result.opponentCount===0&&result.opponentDiagnosticReason
            ?" Motivo: "+result.opponentDiagnosticReason:"")
        :(result.candidateCardCount??0)>0
          ?`${result.candidateCardCount} cartas candidatas encontradas, aguardando validação.`
          :"Análise concluída, mas as cartas continuam não identificadas. O scanner preservou as evidências para investigação.")
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
      {comparison&&<div className="mt-3 rounded-lg border border-line/70 bg-background/50 p-3">
        <p className="text-sm font-semibold text-primary">
          Comparação: referência {comparison.positiveBaselineFingerprint}
        </p>
        <p className="mt-1 text-xs text-muted">
          {comparison.comparedProfiles} mod(s) comparados; {comparison.skippedProfiles} sem análise disponível.
          As diferenças não comprovam IDs, RANK, drops nem fusões.
        </p>
        <div className="mt-2 space-y-1">
          {comparison.compared.map((entry,i)=><p key={entry.romFingerprint??String(i)}
            className="text-xs text-muted">
            <span className="font-semibold text-primary">{mods.find(m=>m.sha256.startsWith(entry.romFingerprint??"-"))?.name??entry.romFingerprint}</span>:
            {" "}{entry.differences.length} diferenças
            {entry.differences.length>0&&" ("+Array.from(new Set(entry.differences.map(d=>d.stage))).join(", ")+")"}.
            Validação em jogo ainda necessária.
          </p>)}
        </div>
        <button type="button" className="btn-ghost mt-3"
          onClick={()=>void navigator.clipboard.writeText(JSON.stringify(comparison,null,2))
            .then(()=>setMessage("Resumo estrutural copiado. Cole-o nesta conversa; não inclui ISO nem receitas."))
            .catch(()=>setMessage("Não foi possível copiar automaticamente. Confira a permissão da área de transferência."))}>
          <ClipboardCopy className="size-4"/> Copiar resumo estrutural
        </button>
      </div>}
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
                  {active&&mod.level==="desconhecido"?"Modo básico":
                    active&&mod.requiresReview?"Ativo · compatibilidade parcial":
                    active?"Pronto para jogar":
                    mod.requiresReview?"Compatibilidade limitada":"Disponível"}
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
              {mod.cardEvidence==="extraidas_estruturalmente"&&<p className="mt-3 text-xs text-gold">
                Cartas extraídas do próprio executável, mas a identidade dos IDs ainda não foi confirmada em jogo. Oponentes e drops permanecem separados.
              </p>}
              {mod.opponentEvidence==="extraidos_estruturalmente"&&<p className="mt-3 text-xs text-gold">
                {mod.opponents} adversários recuperados do executável. IDs ainda não confirmados em jogo; drops e RANK não são liberados por essa hipótese.
              </p>}
              {(mod.modFamilyEvidence?.consecutiveBlocks??0)>0&&<p className="mt-3 text-xs text-muted">
                <span className="font-semibold text-primary">Detecção MultiMod (scanner rev. {mod.modFamilyEvidence!.scanRevision}):</span>{" "}
                {mod.modFamilyEvidence!.consecutiveBlocks} blocos consecutivos e{" "}
                {mod.modFamilyEvidence!.structuralMatrices} matrizes estruturais de pesos.{" "}
                {mod.modFamilyEvidence!.possible39Windows>1
                  ?`${mod.modFamilyEvidence!.possible39Windows} possíveis janelas de 39 adversários; a correspondência permanece ambígua.`
                  :"Associação aos IDs de adversários ainda não verificada."}
                {" "}Nenhum drop ou grupo RANK foi ativado a partir dessas evidências.
              </p>}
              {typeof mod.scanParserRevision==="number"&&mod.scanParserRevision<29&&<p className="mt-3 text-xs text-gold">
                Este perfil foi analisado antes da revisão 29. Clique em Atualizar dados para identificar famílias de tabelas.
              </p>}
              {!mod.opponents&&((mod.opponentCandidateCount??0)>0||Boolean(mod.opponentDiagnosticReason))&&<p className="mt-3 text-xs text-muted">
                {(mod.opponentCandidateCount??0)>0
                  ?`Até ${mod.opponentCandidateCount} nomes independentes candidatos detectados (não verificados).`
                  :"Nenhuma sequência independente de adversários encontrada nesta região."}
                {mod.opponentDiagnosticReason
                  ?<span className="mt-1 block text-gold">
                    Motivo: {mod.opponentDiagnosticReason}
                  </span>
                  :<span className="mt-1 block text-gold">
                    {typeof mod.scanParserRevision==="number"&&mod.scanParserRevision<19
                      ?"Análise anterior à revisão 19: clique em Atualizar dados para registrar o motivo."
                      :"Motivo ainda não registrado neste perfil. Clique em Atualizar dados e confira o resultado."}
                  </span>}
              </p>}
              {!mod.cards&&(mod.candidateCards??0)>0&&<p className="mt-3 text-xs text-gold">
                ${mod.candidateCards?.toLocaleString("pt-BR")} cartas candidatas em análise. Elas ainda não aparecem na Biblioteca para evitar dados incorretos.
              </p>}
              {!mod.cards&&!(mod.candidateCards??0)&&<p className="mt-3 text-xs text-muted">
                O leitor ainda não localizou uma tabela confiável de cartas neste mod. Atualizar dados executa uma nova investigação da ISO.
              </p>}
              {!mod.cards&&mod.nameDiscoveryStatus&&<p className="mt-1 text-[11px] text-muted">
                Resultado dos nomes: {mod.nameDiscoveryStatus}
              </p>}
              {mod.requiresReview&&<p className="mt-3 text-xs text-muted">
                Alguns recursos deste mod podem não estar disponíveis.
              </p>}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" disabled={busy||!desktopApi()||active}
                  className="btn-gold flex-1 disabled:opacity-40" onClick={()=>{
                    const question=mod.level==="desconhecido"
                      ?"As informações deste mod ainda não foram identificadas. Ativar em modo básico para jogar?"
                      :"Este mod tem compatibilidade parcial. Ativar os recursos disponíveis?"
                    const ok=!mod.requiresReview||window.confirm(question)
                    if(ok)void run(()=>desktopApi()!.activate_mod(mod.sha256,mod.requiresReview),"Mod ativado.")
                  }}>{active?"Mod ativo":"Ativar mod"}</button>
                <button type="button" className="btn-ghost flex-1 disabled:opacity-40"
                  disabled={busy||!desktopApi()} onClick={()=>void rescan(mod)}>
                  <RefreshCcw className="size-4"/> Atualizar dados
                </button>
                {mods.length>1&&<button type="button" className="btn-ghost flex-1 disabled:opacity-40"
                  disabled={busy||!desktopApi()} onClick={()=>void compareIso(mod)}>
                  <Layers className="size-4"/> Comparar ISOs
                </button>}
              </div>
              {(mod.modFamilyEvidence?.possible39Windows??0)>1&&<WindowEvidenceForm mod={mod}/>}
              {active&&<LiveOpponentPanel/>}
              {(mod.modFamilyEvidence?.consecutiveBlocks??0)>=39&&
                <StructuralMatrixExplorer mod={mod}/>}
              {!mod.opponents&&((mod.opponentCandidateCount??0)>0||Boolean(mod.opponentDiagnosticReason))&&<button
                type="button" disabled={busy||!desktopApi()}
                className="mt-3 inline-flex items-center gap-2 rounded-md border border-line/70 px-3 py-2 text-xs text-muted transition-colors hover:border-primary/60 hover:text-white disabled:opacity-40"
                onClick={()=>void copyDiagnostics(mod)}>
                <ClipboardCopy className="size-4"/> Copiar diagnóstico técnico
              </button>}
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
    {page==="mods"&&<>
      <LiveDiagnosticsPanel sha={state?.activeSha??null}/>
      <Mods mods={state?.mods??[]} sha={state?.activeSha??null} configured={Boolean(state?.epsxeConfigured)} onRefresh={refresh}/>
    </>}
    {page==="biblioteca"&&<Library sha={state?.activeSha??null} cards={state?.cards??[]}/>}
    {page==="fusoes"&&<Fusions sha={state?.activeSha??null} cards={state?.cards??[]}/>}
    {page==="drops"&&<DropsPage sha={state?.activeSha??null} cards={state?.cards??[]}/>}
  </div>
}
