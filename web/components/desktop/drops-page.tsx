"use client"

import Image from "next/image"
import {useEffect, useState} from "react"
import {ChevronLeft, ChevronRight, Database, RefreshCcw, Search, ShieldCheck} from "lucide-react"
import {cardWithFrame, desktopApi} from "@/lib/desktop"
import type {DropsPage, DropRow} from "@/lib/desktop"

function DropArtwork({sha,id,name}:{sha:string|null;id:number;name:string}) {
  const [failed,setFailed]=useState(false)
  useEffect(()=>setFailed(false),[sha,id])
  const src=cardWithFrame(sha,id)
  return <div className="relative h-[90px] w-[78px] shrink-0 overflow-hidden rounded border border-gold/40 bg-[#0b1932]">
    {src&&!failed?<Image src={src} alt={"Moldura original e carta "+name} fill unoptimized sizes="78px"
      className="object-fill [image-rendering:pixelated]" onError={()=>setFailed(true)}/>:
      <span className="flex h-full items-center justify-center text-xs text-muted">#{id}</span>}
  </div>
}

function DropCard({row,sha,rankConfirmed}:{row:DropRow;sha:string|null;rankConfirmed:boolean}) {
  return <article className="flex items-center gap-3 rounded-xl border border-gold/20 bg-gradient-to-r from-[#122644] to-[#071426] p-3 transition-colors hover:border-primary/50">
    <DropArtwork sha={sha} id={row.cardId} name={row.cardName}/>
    <div className="min-w-0 flex-1">
      <p className="text-xs text-gold">#{row.cardId} · {row.group}{!rankConfirmed?" (grupo bruto)":""}</p>
      <p className="mt-1 truncate font-semibold text-white" title={row.cardName}>{row.cardName}</p>
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
  const [offset,setOffset]=useState(0)
  const [revision,setRevision]=useState(0)
  const [result,setResult]=useState<DropsPage|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const pageSize=36

  // Nunca reutilizar filtros de um mod em outro perfil SHA.
  useEffect(()=>{
    setOpponent(0)
    setGroup("")
    setQuery("")
    setOffset(0)
    setResult(null)
  },[sha])

  useEffect(()=>{
    let mounted=true
    const api=desktopApi()
    if(!api){setResult(null);setLoading(false);return}
    const timer=window.setTimeout(async()=>{
      if(!mounted)return
      setLoading(true)
      try{
        const response=await api.get_drops(opponent,group,query,offset,pageSize)
        if(mounted){setResult(response);setError(null)}
      }catch(e){
        if(mounted){setResult(null);setError(e instanceof Error?e.message:"Erro ao consultar drops locais.")}
      }finally{if(mounted)setLoading(false)}
    },200)
    return()=>{mounted=false;window.clearTimeout(timer)}
  },[sha,opponent,group,query,offset,revision])

  const options=result?.opponents??[]
  const rankGroups=result?.groups??[]
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
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_1.5fr_auto]">
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
      <h2 className="font-display text-xl font-semibold text-gold">Pontos de RANK</h2>
      {rankRules&&rank&&"note" in rank?<>
        <p className="mt-2 text-sm text-muted">{rank.note}</p>
        <p className="mt-1 text-xs text-primary">Base: {rank.base_points} · Bônus projetado por vitória LP: +{rank.lp_victory_bonus}</p>
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
