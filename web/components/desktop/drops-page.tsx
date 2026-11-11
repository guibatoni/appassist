"use client"

import Image from "next/image"
import {useEffect, useMemo, useState} from "react"
import {ChevronLeft, ChevronRight, RefreshCcw, Search} from "lucide-react"
import {cardArt, cardWithFrame, desktopApi} from "@/lib/desktop"
import {CardInfoDialog} from "./card-info-dialog"
import type {CardPreviewSelection} from "./card-info-dialog"
import type {DropsPage, DropRow, LocalCard} from "@/lib/desktop"

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

function DropCard({row,sha,cardDetails,onPreview}:{
  row:DropRow;sha:string|null;cardDetails:LocalCard|null;
  onPreview:(selection:CardPreviewSelection|null)=>void
}) {
  // O mesmo ID da Biblioteca (perfil da ISO ativa) fornece descrição e efeito.
  // Dados não disponíveis não recebem textos inventados ou de outro mod.
  const card:LocalCard=cardDetails?.id===row.cardId?cardDetails:{
    id:row.cardId,name:row.cardName,type:row.cardType,
    category:row.category,attribute:"",atk:row.atk,def:row.def,
    effect:null,effectSource:null,
  }
  return <button type="button" aria-label={`Ver detalhes e locais de drop de ${row.cardName}`}
    onClick={()=>onPreview({card,fallbackDrop:row})}
    className="flex min-w-0 w-full flex-wrap items-center gap-3 rounded-xl border border-gold/20 bg-gradient-to-r from-[#122644] to-[#071426] p-3 text-left transition-colors hover:border-primary/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
    <DropArtwork sha={sha} id={row.cardId} name={row.cardName}/>
    <div className="min-w-0 flex-1">
      <p className="text-xs text-gold">#{row.cardId} · {row.groupLabel}</p>
      <p className="mt-1 truncate font-semibold text-white" title={row.cardName}>{row.cardName}</p>
      {row.category==="Monstros"&&<p className="mt-1 text-xs tabular-nums text-primary">ATK {row.atk??"—"} · DEF {row.def??"—"}</p>}
      <p className="mt-1 text-xs text-muted">{row.opponentName}</p>
    </div>
    <div className="ml-auto shrink-0 text-right">
      <p className="font-display text-xl font-semibold tabular-nums text-primary">{row.chancePercent.toLocaleString("pt-BR",{maximumFractionDigits:4})}%</p>

    </div>
  </button>
}

export function DropsPage({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const [opponent,setOpponent]=useState(0)
  const [rankFilter,setRankFilter]=useState("")
  const [query,setQuery]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"def"|"type"|"name">("id")
  const [cardType,setCardType]=useState("")
  const [offset,setOffset]=useState(0)
  const [pageSize,setPageSize]=useState(20)
  const [revision,setRevision]=useState(0)
  const [result,setResult]=useState<DropsPage|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const cardsById=useMemo(()=>new Map(cards.map(card=>[card.id,card])),[cards])

  // Nunca reutilizar filtros de um mod em outro perfil SHA.
  useEffect(()=>{
    setOpponent(0)
    setRankFilter("")
    setQuery("")
    setSort("id")
    setCardType("")
    setOffset(0)
    setResult(null)
    setError(null)
    setPreview(null)
  },[sha])

  useEffect(()=>{
    let mounted=true
    const api=desktopApi()
    if(!api){setResult(null);setLoading(false);return}
    const timer=window.setTimeout(async()=>{
      if(!mounted)return
      setLoading(true)
      try{
        const response=await api.get_drops(opponent,"",query,offset,pageSize,sort,cardType,rankFilter)
        if(mounted){
          setResult(response)
          setError(null)
        }
      }catch(e){
        if(mounted){setResult(null);setError(e instanceof Error?e.message:"Erro ao consultar drops locais.")}
      }finally{if(mounted)setLoading(false)}
    },200)
    return()=>{mounted=false;window.clearTimeout(timer)}
  },[sha,opponent,rankFilter,query,offset,sort,cardType,pageSize,revision])

  useEffect(()=>{setPreview(null)},[opponent,rankFilter,query,sort,cardType,offset,revision])

  const options=result?.opponents??[]
  const rankOptions=result?.rankOptions??[]
  const types=result?.cardTypes??[]

  return <div className="flex flex-col gap-4">
    <header className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-3 py-3 sm:px-5 sm:py-4">
      <h1 className="font-display text-2xl font-bold text-gold sm:text-3xl">Biblioteca de Drops</h1>
      <p className="mt-1 text-sm text-muted">Encontre cartas e recompensas dos adversários</p>
    </header>
    <section className="panel rounded-xl p-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-muted">Oponente
          <select className="field w-full px-3 py-2 text-sm" value={opponent}
            onChange={e=>{setOpponent(Number(e.target.value));setOffset(0)}}>
            <option value={0}>Todos os oponentes</option>
            {options.map(o=><option key={o.id} value={o.id}>#{o.id} {o.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">RANK da recompensa
          <select className="field w-full px-3 py-2 text-sm" value={rankFilter}
            onChange={e=>{setRankFilter(e.target.value);setOffset(0)}}>
            <option value="">Todos os RANKs</option>
            {rankOptions.map(rank=><option key={rank} value={rank}>{rank}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Buscar carta
          <span className="field flex items-center gap-2 px-3 py-2"><Search className="size-4 text-primary"/>
            <input value={query} onChange={e=>{setQuery(e.target.value);setOffset(0)}}
              placeholder="Nome, ID, efeito ou descrição" className="min-w-0 flex-1 bg-transparent text-sm outline-none"/>
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
        <label className="flex flex-col gap-1 text-xs text-muted">Itens por página
          <select className="field w-full px-3 py-2 text-sm" aria-label="Drops por página"
            value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setOffset(0)}}>
            {[10,20,30,40,50].map(n=><option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button type="button" className="btn-ghost self-end" onClick={()=>setRevision(x=>x+1)}
          aria-label="Recarregar drops"><RefreshCcw className="size-4"/> Atualizar</button>
      </div>
      {loading&&<p className="mt-3 text-xs text-primary" role="status">Consultando tabelas do mod ativo…</p>}
      {error&&<p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
      {result&&!result.available&&<p className="mt-4 rounded-lg border border-line/50 p-4 text-sm text-muted">Nenhum drop disponível neste mod. Use Atualizar dados na Biblioteca de Mods.</p>}
      {result?.available&&<>
        <div className="dt-adaptive-drops">
          {result.rows.map(row=><DropCard key={row.opponentId+"-"+row.group+"-"+row.cardId}
            row={row} sha={sha} cardDetails={cardsById.get(row.cardId)??null} onPreview={setPreview}/>)}
        </div>
        {!result.rows.length&&<p className="py-8 text-center text-sm text-muted">Nenhuma carta para os filtros selecionados.</p>}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
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
      <CardInfoDialog selection={preview} sha={sha} onClose={()=>setPreview(null)}/>
    </section>
  </div>
}
