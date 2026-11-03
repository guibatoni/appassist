"use client"

import Image from "next/image"
import {useEffect, useState} from "react"
import {ChevronLeft, ChevronRight, Database, RefreshCcw, Search, ShieldCheck} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi} from "@/lib/desktop"
import type {DropsPage, DropRow, DuelEvidence, MipsTraceResult} from "@/lib/desktop"

function DropArtwork({sha,id,name}:{sha:string|null;id:number;name:string}) {
  const [source,setSource]=useState<"frame"|"art"|"none">("frame")
  useEffect(()=>setSource("frame"),[sha,id])
  const src=source==="frame"?cardWithFrame(sha,id):source==="art"?cardArt(sha,id):null
  return <div className="relative h-[90px] w-[78px] shrink-0 overflow-hidden rounded border border-gold/40 bg-[#0b1932]">
    {src?<Image src={src} alt={"Arte extraída da carta "+name} fill unoptimized sizes="78px"
      className={source==="frame"?"object-fill [image-rendering:pixelated]":"object-contain [image-rendering:pixelated]"}
      onError={()=>setSource(source==="frame"?"art":"none")}/>:
      <span className="flex h-full items-center justify-center text-xs text-muted">#{id}</span>}
  </div>
}

function DropCard({row,sha,rankConfirmed}:{row:DropRow;sha:string|null;rankConfirmed:boolean}) {
  return <article className="flex items-center gap-3 rounded-xl border border-gold/20 bg-gradient-to-r from-[#122644] to-[#071426] p-3 transition-colors hover:border-primary/50">
    <DropArtwork sha={sha} id={row.cardId} name={row.cardName}/>
    <div className="min-w-0 flex-1">
      <p className="text-xs text-gold">#{row.cardId} · {row.group}{!rankConfirmed?" (grupo bruto)":""}</p>
      <p className="mt-1 truncate font-semibold text-white" title={row.cardName}>{row.cardName}</p>
      {row.category==="Monstros"&&<p className="mt-1 text-xs tabular-nums text-primary">ATK {row.atk??"—"} · DEF {row.def??"—"}</p>}
      <p className="mt-1 text-xs text-muted">{row.opponentName}</p>
      {row.sourceOffset&&<p className="mt-1 text-[10px] text-muted">WA offset: {row.sourceOffset}</p>}
    </div>
    <div className="shrink-0 text-right">
      <p className="font-display text-xl font-semibold tabular-nums text-primary">{row.chancePercent.toLocaleString("pt-BR",{maximumFractionDigits:4})}%</p>
      <p className="text-xs text-muted">{row.weight}/2048</p>
    </div>
  </article>
}

const POINT_LABELS: Record<string,string> = {
  turns:"Turnos", effective_attacks:"Ataques efetivos", defense_wins:"Vitórias em defesa",
  face_down:"Cartas viradas", spells:"Magias", traps:"Armadilhas",
  cards_used:"Cartas utilizadas", remaining_lp:"Pontos de vida restantes",
  fusions:"Fusões", equips:"Equipamentos",
}

export function DropsPage({sha}:{sha:string|null}) {
  const [opponent,setOpponent]=useState(0)
  const [group,setGroup]=useState("")
  const [query,setQuery]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"def"|"type"|"name">("id")
  const [cardType,setCardType]=useState("")
  const [offset,setOffset]=useState(0)
  const [revision,setRevision]=useState(0)
  const [result,setResult]=useState<DropsPage|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [duelEvidence,setDuelEvidence]=useState<DuelEvidence|null>(null)
  const [traceInfo,setTraceInfo]=useState<MipsTraceResult|null>(null)
  const [traceBusy,setTraceBusy]=useState(false)
  const [traceError,setTraceError]=useState<string|null>(null)
  const [obsOpponent,setObsOpponent]=useState(0)
  const [obsRank,setObsRank]=useState("Z-POW")
  const [obsCard,setObsCard]=useState("")
  const [obsPoints,setObsPoints]=useState("")
  const [obsVictory,setObsVictory]=useState("lp")
  const [obsBusy,setObsBusy]=useState(false)
  const [obsError,setObsError]=useState<string|null>(null)
  const pageSize=36

  // Nunca reutilizar filtros de um mod em outro perfil SHA.
  useEffect(()=>{
    setOpponent(0)
    setGroup("")
    setQuery("")
    setSort("id")
    setCardType("")
    setOffset(0)
    setResult(null)
    setDuelEvidence(null)
    setTraceInfo(null)
    setTraceError(null)
    setObsOpponent(0)
    setObsCard("")
    setObsPoints("")
    setObsError(null)
  },[sha])

  useEffect(()=>{
    let mounted=true
    const api=desktopApi()
    if(!api){setResult(null);setLoading(false);return}
    const timer=window.setTimeout(async()=>{
      if(!mounted)return
      setLoading(true)
      try{
        const response=await api.get_drops(opponent,group,query,offset,pageSize,sort,cardType)
        if(mounted){setResult(response);setError(null)}
      }catch(e){
        if(mounted){setResult(null);setError(e instanceof Error?e.message:"Erro ao consultar drops locais.")}
      }finally{if(mounted)setLoading(false)}
    },200)
    return()=>{mounted=false;window.clearTimeout(timer)}
  },[sha,opponent,group,query,offset,sort,cardType,revision])

  useEffect(()=>{
    let active=true
    const api=desktopApi()
    if(api)void api.get_rank_trace_status().then(data=>{
      if(active)setTraceInfo(data)
    }).catch(()=>{if(active)setTraceInfo(null)})
    return()=>{active=false}
  },[sha,revision])
  const importTrace=async()=>{
    const api=desktopApi()
    if(!api)return
    setTraceBusy(true)
    setTraceError(null)
    try{
      const result=await api.import_rank_trace()
      if(!result.cancelled)setTraceInfo({status:"updated",last:result,records:(traceInfo?.records??0)+1})
    }catch(e){
      setTraceError(e instanceof Error?e.message:"Não foi possível importar log MIPS.")
    }finally{setTraceBusy(false)}
  }
  useEffect(()=>{
    let active=true
    const api=desktopApi()
    if(api)void api.get_duel_evidence().then(data=>{
      if(active)setDuelEvidence(data)
    }).catch(()=>{if(active)setDuelEvidence(null)})
    return()=>{active=false}
  },[sha,revision])
  const saveObservation=async()=>{
    const id=Number(obsCard),points=obsPoints.trim()?Number(obsPoints):null
    if(!Number.isInteger(obsOpponent)||obsOpponent<1||!Number.isInteger(id)||id<1||id>722||
      (points!==null&&(!Number.isInteger(points)||points<0||points>300))){
      setObsError("Selecione o oponente, ID de carta válido e pontuação entre 0 e 300.")
      return
    }
    const api=desktopApi()
    if(!api)return
    setObsBusy(true)
    setObsError(null)
    try{
      const report=await api.record_duel_result(obsOpponent,obsRank,id,points,obsVictory)
      setDuelEvidence(report)
      setObsCard("")
      setObsPoints("")
    }catch(e){
      setObsError(e instanceof Error?e.message:"Falha ao registrar duelo observado.")
    }finally{setObsBusy(false)}
  }

  const options=result?.opponents??[]
  const rankGroups=result?.groups??[]
  const types=result?.cardTypes??[]
  const rank=result?.rankPoints
  const rankRules=rank&&"available" in rank&&rank.available?rank.rules:null

  return <div className="flex flex-col gap-4">
    <header className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-5 py-4">
      <h1 className="font-display text-2xl font-bold text-gold sm:text-3xl">Biblioteca de Drops</h1>
      <p className="mt-1 text-sm text-muted">Oponentes e probabilidades extraídos automaticamente dos arquivos da ISO ativa</p>
    </header>
    <section className="panel rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="inline-flex items-center gap-2"><Database className="size-4 text-primary"/> {result?.source??"WA_MRG.MRG + SLUS_014.11"}</span>
        <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4 text-primary"/> Sem dados herdados de outros mods</span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-muted">Oponente
          <select className="field w-full px-3 py-2 text-sm" value={opponent}
            onChange={e=>{setOpponent(Number(e.target.value));setOffset(0)}}>
            <option value={0}>Todos os oponentes</option>
            {options.map(o=><option key={o.id} value={o.id}>#{o.id} {o.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Tabela de drop
          <select className="field w-full px-3 py-2 text-sm" value={group}
            onChange={e=>{setGroup(e.target.value);setOffset(0)}}>
            <option value="">Todos os grupos</option>
            {rankGroups.map(g=><option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Buscar carta
          <span className="field flex items-center gap-2 px-3 py-2"><Search className="size-4 text-primary"/>
            <input value={query} onChange={e=>{setQuery(e.target.value);setOffset(0)}}
              placeholder="Nome ou ID da carta" className="min-w-0 flex-1 bg-transparent text-sm outline-none"/>
          </span>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Ordenar cartas
          <select className="field w-full px-3 py-2 text-sm" value={sort}
            onChange={e=>{setSort(e.target.value as typeof sort);setOffset(0)}}>
            <option value="id">ID / ordem das tabelas</option>
            <option value="atk">Maior ataque</option><option value="def">Maior defesa</option>
            <option value="type">Tipo</option><option value="name">Alfabética (A–Z)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Tipo da carta
          <select className="field w-full px-3 py-2 text-sm" value={cardType}
            onChange={e=>{setCardType(e.target.value);setOffset(0)}}>
            <option value="">Todos os tipos</option>
            {types.map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <button type="button" className="btn-ghost self-end" onClick={()=>setRevision(x=>x+1)}
          aria-label="Recarregar drops"><RefreshCcw className="size-4"/> Atualizar</button>
      </div>
      {loading&&<p className="mt-3 text-xs text-primary" role="status">Consultando tabelas do mod ativo…</p>}
      {error&&<p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
      {result&&!result.available&&<p className="mt-4 rounded-lg border border-gold/30 p-4 text-sm text-gold">{result.status}. Use a ISO compatível na Biblioteca de Mods e reanalise os dados.</p>}
      {result?.available&&<>
        <p className="mt-3 text-xs text-muted">{result.status}</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {result.rows.map(row=><DropCard key={row.opponentId+"-"+row.group+"-"+row.cardId}
            row={row} sha={sha} rankConfirmed={result.rankLabelsVerified}/>)}
        </div>
        {!result.rows.length&&<p className="py-8 text-center text-sm text-muted">Nenhuma carta para os filtros selecionados.</p>}
        <div className="mt-4 flex items-center justify-between gap-2">
          <p className="text-xs tabular-nums text-muted">{result.total?offset+1:0}–{Math.min(offset+pageSize,result.total)} de {result.total} drops</p>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost disabled:opacity-30" disabled={offset===0||loading}
              onClick={()=>setOffset(x=>Math.max(0,x-pageSize))}><ChevronLeft className="size-4"/> Anterior</button>
            <button type="button" className="btn-ghost disabled:opacity-30"
              disabled={offset+pageSize>=result.total||loading}
              onClick={()=>setOffset(x=>x+pageSize)}>Próxima <ChevronRight className="size-4"/></button>
          </div>
        </div>
      </>}
    </section>
    <section className="panel rounded-xl p-4">
      <h2 className="font-display text-xl font-semibold text-gold">Conferir drops obtidos em duelo</h2>
      <p className="mt-1 text-sm text-muted">Após o duelo, registre o RANK e o ID da carta exibidos no jogo. O DUELTRACE compara com os três bancos do oponente da ISO ativa, sem copiar dados de outros mods.</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-muted">Oponente do duelo
          <select className="field px-3 py-2 text-sm" value={obsOpponent}
            onChange={e=>setObsOpponent(Number(e.target.value))}>
            <option value={0}>Selecione o oponente</option>
            {options.map(o=><option key={o.id} value={o.id}>#{o.id} {o.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">RANK observado
          <select className="field px-3 py-2 text-sm" value={obsRank}
            onChange={e=>setObsRank(e.target.value)}>
            {["Z-POW","S-POW","S-TEC"].map(v=><option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Resultado do duelo
          <select className="field px-3 py-2 text-sm" value={obsVictory}
            onChange={e=>setObsVictory(e.target.value)}>
            <option value="lp">Vitória por LP</option>
            <option value="deckout">Vitória por deck-out</option>
            <option value="other">Outro resultado</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">ID da carta recebida
          <input type="number" min={1} max={722} value={obsCard}
            onChange={e=>setObsCard(e.target.value)} className="field px-3 py-2 text-sm"
            placeholder="Ex.: 123"/>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Pontos exibidos (opcional)
          <input type="number" min={0} max={300} value={obsPoints}
            onChange={e=>setObsPoints(e.target.value)} className="field px-3 py-2 text-sm"
            placeholder="Ex.: 95"/>
        </label>
        <button type="button" disabled={obsBusy||!result?.available||!desktopApi()}
          className="btn-gold self-end disabled:opacity-40" onClick={()=>void saveObservation()}>
          {obsBusy?"Registrando…":"Registrar resultado"}
        </button>
      </div>
      {obsError&&<p className="mt-2 text-sm text-danger" role="alert">{obsError}</p>}
      <div className="mt-3 text-xs text-muted">
        Registros locais: {duelEvidence?.observations??0} · Evidências discriminantes:
        {" "}{duelEvidence?.usable??0} · Ambíguas: {duelEvidence?.ambiguous??0}
        {" "}· Divergentes: {duelEvidence?.inconsistent??0}
      </div>
      {duelEvidence?.scoreComparisons?.compared ? <p className="mt-2 text-xs text-primary">
        Projeção de RANK × pontos mostrados: {duelEvidence.scoreComparisons.exact}
        {" "}coerentes em {duelEvidence.scoreComparisons.compared} vitórias por LP.
        {" "}Coerência não comprova execução da rotina MIPS.
      </p>:null}
      {duelEvidence?.suspectedMappings&&Object.entries(duelEvidence.suspectedMappings).length>0&&
        <div className="mt-3 rounded-lg border border-gold/30 bg-background/40 p-3 text-xs text-gold">
          Correspondência sugerida por observações manuais (não comprovada pela execução MIPS):
          {Object.entries(duelEvidence.suspectedMappings).map(([rank,m])=>
            <p key={rank} className="mt-1">{rank}: {m.group} · {m.observations} duelos, {m.opponents} oponentes</p>)}
        </div>}
      {duelEvidence?.mismatches?.length ? <p className="mt-3 text-xs text-danger">
        Atenção: {duelEvidence.mismatches.length} divergência(s) entre os drops registrados e as tabelas do WA. Confira o mod ativo, o oponente e o RANK observado.
      </p>:null}
      <p className="mt-2 text-xs text-muted">Esses registros são relatos manuais de cada duelo. Eles não confirmam sozinhos as instruções MIPS executadas ou a fórmula de RANK.</p>
      <div className="mt-4 border-t border-line/50 pt-3">
        <h3 className="font-semibold text-gold">Auditoria de execução MIPS do duelo</h3>
        <p className="mt-1 text-xs text-muted">
          Importe um arquivo .log ou .txt de instruções executadas exportado pelo depurador do emulador durante um duelo.
          O analisador compara os PCs executados com os candidatos do SLUS deste mod, sem enviar o log para a internet.
        </p>
        <button type="button" className="btn-ghost mt-2" disabled={traceBusy||!desktopApi()}
          onClick={()=>void importTrace()}>{traceBusy?"Analisando log…":"Importar log MIPS de duelo"}</button>
        {traceError&&<p className="mt-2 text-xs text-danger" role="alert">{traceError}</p>}
        {traceInfo?.last&&<div className="mt-2 text-xs text-muted">
          <p>Último trace: {traceInfo.last.status} · PCs distintos: {traceInfo.last.distinctPCs??"—"}
            {" "}· Instruções amostradas: {traceInfo.last.instructionSamples??"—"}</p>
          {traceInfo.last.executedCandidates?.map(x=>
            <p key={x.pc} className="mt-1 text-primary">{x.pc}: {x.hits} execução(ões) observada(s)</p>)}
          <p className="mt-1 text-gold">PC executado não confirma por si só a rotina responsável pela pontuação RANK.</p>
        </div>}
      </div>
    </section>
    <section className="panel rounded-xl p-4">
      <h2 className="font-display text-xl font-semibold text-gold">Pontos de RANK</h2>
      {rankRules&&rank&&"note" in rank?<>
        <p className="mt-2 text-sm text-muted">{rank.note}</p>
        <p className="mt-2 text-xs font-semibold text-gold">
          {rank.binary_verified
            ? "Modelo X15 verificado por hashes da ISO, do SLUS e da tabela · duelo ainda não confirmado"
            : rank.structure_verified
              ? "Pontos extraídos automaticamente de 40 cópias do WA · rotina MIPS ainda não verificada"
              : "Análise preliminar · pontuação do duelo ainda não confirmada"}
        </p>
        {rank.base_points!==null&&rank.lp_victory_bonus!==null&&
          <p className="mt-1 text-xs text-primary">Base: {rank.base_points} · Bônus por vitória LP: +{rank.lp_victory_bonus}</p>}
        {rank.table_count&&
          <p className="mt-1 text-xs text-muted">
            Cópias estruturais validadas: {rank.table_count}
            {typeof rank.first_offset==="number"&&
              <> · Offset identificado: 0x{rank.first_offset.toString(16).toUpperCase()}</>}
            {rank.layout_moved&&" · Layout diferente do X15"}
            {typeof rank.repeat_stride==="number"&&
              <> · Espaçamento: {rank.repeat_stride} bytes</>}
            {" · SHA: "}{rank.table_sha256?.slice(0,16)??"—"}…
          </p>}
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {Object.entries(rankRules).map(([name,thresholds])=><div key={name}
            className="rounded-lg border border-line/60 bg-background/40 p-3">
            <p className="mb-2 font-semibold text-white">{POINT_LABELS[name]??name}</p>
            <div className="flex flex-wrap gap-1.5 text-xs">{thresholds.map((step,i)=>
              <span key={i} className="rounded border border-primary/20 px-2 py-1 text-primary">
                &lt; {step.below}: {step.points>0?"+":""}{step.points}
              </span>)}</div>
          </div>)}
        </div>
      </>:<p className="mt-2 text-sm text-muted">Os pontos de RANK ainda não foram identificados com segurança para esta ISO. Não usamos fórmulas do X15 em mods desconhecidos.</p>}
      <p className="mt-3 text-xs text-muted">Tabela de pontuação não equivale a resultado final do duelo. Modelos e endereços RAM exigem validação individual por mod.</p>
    </section>
  </div>
}
