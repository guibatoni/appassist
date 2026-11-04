"use client"

import Image from "next/image"
import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, FilePlus2, Gamepad2,
  GitMerge, Layers, Play, RefreshCcw, Search, Shield, Swords, Upload,
} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi, sourceLabel, useDesktopState} from "@/lib/desktop"
import {DropsPage} from "./drops-page"
import type {LocalCard, HandState, FusionPage, LocalMod, RankState, RankDiagnostic, CardMatchResult, CardAIMatchReport, ModScanDiagnostic} from "@/lib/desktop"

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
  const [lp,setLp]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [diagnostic,setDiagnostic]=useState<RankDiagnostic|null>(null)
  const [diagnosing,setDiagnosing]=useState(false)
  const [reanalysing,setReanalysing]=useState(false)
  const [feedback,setFeedback]=useState<string|null>(null)
  const [captured,setCaptured]=useState<string|null>(null)

  useEffect(()=>{
    let mounted=true,reading=false
    setRank(null)
    setDiagnostic(null)
    setFeedback(null)
    setCaptured(null)
    setLp(null)
    const read=async()=>{
      const api=desktopApi()
      if(!api||reading)return
      reading=true
      try{
        const value=await api.get_rank()
        if(mounted)setRank(value)
      }catch{
        if(mounted)setRank({ready:false,state:"unavailable",
          status:"Não foi possível comunicar com o leitor de RANK.",
          score:null,category:null,counters:null})
      }finally{reading=false}
    }
    void read()
    const interval=window.setInterval(()=>void read(),850)
    return()=>{mounted=false;window.clearInterval(interval)}
  },[sha])

  // O LP lido da RAM já é o valor inicial do campo. Na v0.9.0 ele
  // era só placeholder e o botão ficava desativado, mesmo com 10000.
  // O usuário continua comparando o valor com o HUD antes de confirmar.
  const effectiveLp=lp??(typeof rank?.candidateLp==="number"?String(rank.candidateLp):"")
  const confirmLp=async()=>{
    const numeric=Number(effectiveLp)
    if(!/^\d{1,5}$/.test(effectiveLp)||!Number.isInteger(numeric)||numeric<0||numeric>32766)return
    const api=desktopApi()
    if(!api)return
    setBusy(true)
    setFeedback(null)
    try{
      const confirmed=await api.confirm_rank_lp(numeric)
      setRank(confirmed)
      if(confirmed.state==="lp_mismatch")setLp(null)
    }
    catch(e){setFeedback(e instanceof Error?e.message:"Falha ao confirmar LP.")}
    finally{setBusy(false)}
  }
  const investigate=async()=>{
    const api=desktopApi()
    if(!api)return
    setDiagnosing(true)
    setFeedback(null)
    try{setDiagnostic(await api.get_rank_diagnostic())}
    catch(e){setFeedback(e instanceof Error?e.message:"Diagnóstico indisponível.")}
    finally{setDiagnosing(false)}
  }
  const reanalyse=async()=>{
    const api=desktopApi()
    if(!api||!sha)return
    setReanalysing(true)
    setFeedback(null)
    try{
      await api.scan_sources(sha)
      const [state,details]=await Promise.all([api.get_rank(),api.get_rank_diagnostic()])
      setRank(state)
      setDiagnostic(details)
      setFeedback(details.readyForLiveRead
        ?"Perfil atualizado. Inicie um duelo e confirme os LP, se solicitado."
        :"Perfil relido. O mapeamento RAM desta ISO ainda precisa ser validado.")
    }catch(e){setFeedback(e instanceof Error?e.message:"Não foi possível reanalisar a ISO.")}
    finally{setReanalysing(false)}
  }
  const capture=async()=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true)
    setFeedback(null)
    try{const result=await api.capture_rank_prediction();setCaptured(
      result.ready?`${result.score??"—"} pontos · ${result.category??"—"}`:"Captura indisponível.")}
    catch(e){setFeedback(e instanceof Error?e.message:"Falha na captura.")}
    finally{setBusy(false)}
  }

  const ready=rank?.ready===true
  const needsLp=rank?.state==="needs_lp_confirmation"||rank?.state==="lp_mismatch"
  const pending=rank?.state==="unsupported"
  const observing=rank?.state==="needs_ram_validation"
  const experimental=rank?.sourceMode==="experimental"
  const status=ready?(experimental?"Em teste":"Leitura ativa"):
    needsLp?"Confirme seus LP":observing?"Testando RAM":
    pending?"Sem perfil":"Aguardando leitura"
  const rankSystem=rank?.rankSystem==="x15"?"Remaster X15":
    rank?.rankSystem==="classic"?"RANK original":"RANK por ISO"
  const details=rank?.victorySource==="ram_deckout"?"Marcador X15: deck-out":
    rank?.victorySource==="ram_lp"?"Marcador X15: vitória por LP":
    "Projeção se vencer por LP"
  return <section className="panel rounded-xl p-4" aria-label="RANK ao vivo">
    <div className="flex items-center justify-between gap-2">
      <h2 className="font-display text-lg font-semibold text-gold">RANK ao vivo</h2>
      <span className={"text-xs font-medium "+(ready?(experimental?"text-gold":"text-success"):"text-muted")} role="status">
        {ready?"●":"○"} {status}
      </span>
    </div>
    <div className="mt-4 rounded-lg border border-primary/20 bg-background/60 px-4 py-4 text-center">
      <p className="text-xs text-muted">{ready?(experimental?"Projeção experimental · vitória por LP":details):"Aguardando leitura confiável"}</p>
      <p className="mt-1 font-display text-4xl font-bold tabular-nums text-primary">
        {ready?rank.score:"—"} <span className="text-sm font-normal text-muted">pts</span>
      </p>
      <p className="mt-1 font-display text-xl font-bold text-gold">
        {ready?rank.category:needsLp?"Confirme os LP":observing?"Validando contadores":"RANK indisponível"}
      </p>
      <p className="mt-1 text-[11px] text-muted">
        {rankSystem} · {ready?(experimental?"RAM antiga em teste; não validada":"Estimativa, não resultado oficial"):"Sem projeção confiável"}
      </p>
    </div>
    {ready&&rank.counters&&
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span>Turnos <strong className="text-white">{rank.counters.turns??"—"}</strong></span>
        <span>LP <strong className="text-white">{rank.counters.remaining_lp??"—"}</strong></span>
        <span>Fusões <strong className="text-white">{rank.counters.fusions??"—"}</strong></span>
      </div>}
    {needsLp&&<div className="mt-3 space-y-2">
      <p className="text-xs text-muted">
        Confira se o valor detectado corresponde aos LP exibidos no ePSXe.
        Se estiver correto, clique em Confirmar. As próximas ações serão lidas automaticamente.
      </p>
      <div className="flex gap-2">
        <input aria-label="LP exibidos no jogo" type="number" min={0} max={32766}
          placeholder="LP do jogo" value={effectiveLp}
          onChange={e=>setLp(e.target.value)}
          className="field w-full min-w-0 rounded-md px-2 py-2 text-sm"/>
        <button type="button" className="btn-gold shrink-0 disabled:opacity-40"
          disabled={!/^\d{1,5}$/.test(effectiveLp)||busy} onClick={()=>void confirmLp()}>Confirmar LP</button>
      </div>
    </div>}
    {observing&&
      <p className="mt-3 text-xs text-gold" role="status">
        LP confirmados. Faça duas ações normais no duelo para testar a leitura antiga
        ({rank?.validationProgress??0}/{rank?.validationRequired??2} mudanças identificadas).
      </p>}
    {ready&&experimental&&
      <p className="mt-3 text-xs text-gold">
        Leitura experimental: os pontos são estimados com a fórmula antiga,
        mas a estrutura RAM desta ISO ainda não foi comprovada em duelos reais.
      </p>}
    {!ready&&!needsLp&&!observing&&
      <p className="mt-3 text-xs text-muted">
        {pending?"Selecione uma ISO para iniciar a leitura de RAM.":
          rank?.status??"Conectando ao ePSXe…"}
      </p>}
    <details className="mt-3 border-t border-line/60 pt-2 text-xs text-muted">
      <summary className="cursor-pointer select-none py-1 text-primary">
        Diagnóstico e ferramentas
      </summary>
      <p className="mt-2">{rank?.status??"Aguardando dados do emulador."}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" className="btn-ghost disabled:opacity-40"
          disabled={!sha||diagnosing||reanalysing} onClick={()=>void investigate()}>
          {diagnosing?"Analisando…":"Diagnosticar ISO"}
        </button>
        {rank?.diagnosticCode==="rank_table_missing"&&
          <button type="button" className="btn-ghost disabled:opacity-40"
            disabled={!sha||reanalysing||diagnosing} onClick={()=>void reanalyse()}>
            {reanalysing?"Relendo ISO…":"Reanalisar perfil"}
          </button>}
        {ready&&!experimental&&<button type="button" className="btn-ghost disabled:opacity-40"
          disabled={busy} onClick={()=>void capture()}>Capturar previsão</button>}
      </div>
      {diagnostic&&<p className="mt-2">
        {diagnostic.reason} {diagnostic.nextStep}
        {" "}RAM validada: {diagnostic.ramBindingVerified?"sim":"não"}.
        {diagnostic.legacyProbeAvailable&&" Leitura do Assistente antigo disponível em modo experimental."}
      </p>}
      {captured&&<p className="mt-2 text-success">Capturado: {captured}</p>}
      {feedback&&<p className="mt-2 text-gold" role="status">{feedback}</p>}
    </details>
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
                <p className="mt-1 text-xs text-muted">{sourceLabel(item.validation)}</p>
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
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState<string|null>(null)
  const [diagnostics,setDiagnostics]=useState<Record<string,ModScanDiagnostic>>({})
  const [diagnosing,setDiagnosing]=useState<string|null>(null)
  const investigate=async(mod:LocalMod,ollama=false)=>{
    const api=desktopApi()
    if(!api)return
    setDiagnosing(mod.sha256);setMessage(null)
    try{
      const result=await api.get_mod_scan_diagnostic(mod.sha256,ollama)
      setDiagnostics(old=>({...old,[mod.sha256]:result}))
    }catch(e){setMessage(e instanceof Error?e.message:"Diagnóstico não disponível.")}
    finally{setDiagnosing(null)}
  }
  const rescan=async(mod:LocalMod)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true);setMessage(null)
    try{
      const result=await api.scan_sources(mod.sha256)
      await onRefresh()
      if(result.diagnostic){
        setDiagnostics(old=>({...old,[mod.sha256]:result.diagnostic!}))
      }
      setMessage(
        result.diagnostic&&!result.diagnostic.automaticExtractionComplete
          ?"Estrutura não identificada: "+(result.diagnostic.issues[0]??"O scanner não validou as tabelas.")+
            " · Ollama: "+(result.aiState??"não disponível")+
            ". Consulte o diagnóstico deste mod."
          :"Extração concluída: "+result.opponentCount+" oponentes, "+
            result.dropEntries+" drops e "+result.artCount+" artes. "+
            "Ollama: "+(result.aiState??"não iniciada")+".")
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
          {mod.cards===0&&<p className="mt-2 text-xs text-gold">
            Estrutura não reconhecida. Zero cartas extraídas não significa que a ISO não contenha cartas.
          </p>}
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className="btn-ghost flex-1 disabled:opacity-40"
              disabled={busy||diagnosing!==null||!desktopApi()}
              onClick={()=>void investigate(mod,false)}>
              {diagnosing===mod.sha256?"Analisando…":"Diagnosticar estrutura"}
            </button>
            <button type="button" className="btn-ghost flex-1 disabled:opacity-40"
              disabled={busy||diagnosing!==null||!desktopApi()}
              onClick={()=>void investigate(mod,true)}>
              {diagnosing===mod.sha256?"Consultando…":"Investigar com Ollama"}
            </button>
          </div>
          {diagnostics[mod.sha256]&&<div className="mt-3 rounded-lg border border-primary/30 bg-background/60 p-3 text-xs text-muted">
            <p className="font-semibold text-primary">Diagnóstico do layout: {diagnostics[mod.sha256].state.replaceAll("_"," ")}</p>
            <p className="mt-1">Arquivos indexados: {diagnostics[mod.sha256].indexedFiles}.
              {" "}Setores: {diagnostics[mod.sha256].sectorBytes??"não identificados"} bytes.</p>
            <p className="mt-1">Executável: {diagnostics[mod.sha256].chosenExecutable||"não reconhecido"}.
              {" "}WA: {diagnostics[mod.sha256].chosenWa||"não reconhecido"}.</p>
            <p className="mt-1">SYSTEM.CNF: {diagnostics[mod.sha256].systemCnf?.status??"não analisado"}
              {diagnostics[mod.sha256].systemCnf?.bootTarget
                ? " · BOOT: "+diagnostics[mod.sha256].systemCnf.bootTarget:""}
            </p>
            {diagnostics[mod.sha256].issues.map((issue,i)=>
              <p className="mt-1 text-gold" key={"issue-"+i}>{issue}</p>)}
            <details className="mt-2">
              <summary className="cursor-pointer text-primary">Evidências e próximas investigações</summary>
              {diagnostics[mod.sha256].files?.length>0&&<div className="mt-2">
                <p className="font-semibold text-primary">Arquivos encontrados no disco:</p>
                <div className="mt-1 max-h-56 overflow-y-auto rounded border border-line/50 p-2">
                  {diagnostics[mod.sha256].files.map((file,i)=>
                    <p key={i} className="break-all py-0.5">
                      {file.name} · {file.size===null?"tamanho não identificado":file.size.toLocaleString("pt-BR")+" bytes"}
                    </p>)}
                </div>
              </div>}
              {diagnostics[mod.sha256].executableCandidates.length>0&&
                <p className="mt-2 break-words">Executáveis candidatos: {diagnostics[mod.sha256].executableCandidates.join(", ")}</p>}
              {diagnostics[mod.sha256].waCandidates.length>0&&
                <p className="mt-1 break-words">Arquivos WA candidatos: {diagnostics[mod.sha256].waCandidates.join(", ")}</p>}
              {diagnostics[mod.sha256].nextSteps.map((step,i)=><p key={"step-"+i} className="mt-1">{i+1}. {step}</p>)}
            </details>
            {diagnostics[mod.sha256].ai&&diagnostics[mod.sha256].ai!.state!=="nao_solicitada"&&
              <div className="mt-2 border-t border-line/60 pt-2">
                <p className="font-semibold text-primary">Ollama: {diagnostics[mod.sha256].ai!.state.replaceAll("_"," ")}</p>
                {diagnostics[mod.sha256].ai!.message&&<p className="mt-1">{diagnostics[mod.sha256].ai!.message}</p>}
                {diagnostics[mod.sha256].ai!.resumo&&<p className="mt-1">{diagnostics[mod.sha256].ai!.resumo}</p>}
                {diagnostics[mod.sha256].ai!.prioridades?.map((step,i)=><p key={"ai-"+i} className="mt-1">{i+1}. {step}</p>)}
              </div>}
          </div>}
        </div>)}
      </div>
      {!mods.length&&<Empty>Nenhum mod cadastrado. Importe uma ISO/BIN na versão Windows. Os arquivos não são enviados ao Vercel.</Empty>}
    </section>
    <CardMatchPanel mods={mods} activeSha={sha}/>
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
