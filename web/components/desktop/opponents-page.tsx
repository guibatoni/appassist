"use client"

import {T,useI18n} from "@/lib/i18n"

import {useEffect,useMemo,useState} from "react"
import {ChevronDown,Gift,RefreshCcw,Search,Users} from "lucide-react"
import {desktopApi} from "@/lib/desktop"
import type {LocalCard,OpponentDeck,DropsPage as DropsModel} from "@/lib/desktop"
import {CardFace} from "./deck-card-face"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"

export function OpponentsPage({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const {t}=useI18n()
  const [selected,setSelected]=useState(0)
  const [query,setQuery]=useState("")
  const [result,setResult]=useState<OpponentDeck|null>(null)
  const [drops,setDrops]=useState<DropsModel|null>(null)
  const [dropsError,setDropsError]=useState("")
  const [showDrops,setShowDrops]=useState(false)
  const [error,setError]=useState("")
  const [loading,setLoading]=useState(false)
  const [refresh,setRefresh]=useState(0)
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const byId=useMemo(()=>new Map(cards.map(card=>[card.id,card])),[cards])

  useEffect(()=>{
    setSelected(0);setResult(null);setShowDrops(false);setDrops(null)
    setDropsError("");setPreview(null);setError("");setQuery("")
  },[sha])
  useEffect(()=>{
    let live=true
    const api=desktopApi()
    if(!sha||!api){setResult(null);return}
    setLoading(true)
    void api.get_opponent_deck(selected).then(v=>{
      if(live){setResult(v);setError("");setSelected(v.opponentId)}
    }).catch(e=>{if(live){setResult(null);setError(String(e))}})
      .finally(()=>{if(live)setLoading(false)})
    return()=>{live=false}
  },[sha,selected,refresh])
  useEffect(()=>{
    let live=true
    setDrops(null)
    setDropsError("")
    if(!showDrops||!sha||!selected)return
    const api=desktopApi()
    if(!api)return
    void api.get_drops(selected,"","",0,100,"id","","").then(v=>{
      if(live){setDrops(v);setDropsError("")}
    }).catch(e=>{
      if(live){setDrops(null);setDropsError(e instanceof Error?e.message:String(e))}
    })
    return()=>{live=false}
  },[sha,selected,showDrops,refresh])

  const rows=(result?.cards??[]).filter(c=>
    (c.name+" "+c.type+" "+c.id).toLowerCase().includes(query.toLowerCase().trim()))
  const selectCard=(id:number)=>{
    const card=byId.get(id)
    if(card)setPreview({card})
  }
  return <section className="flex flex-col gap-4">
    <div className="panel rounded-xl border-gold/35 bg-gradient-to-r from-[#142b51] to-[#061126] p-4">
      <div className="flex items-center gap-3"><Users className="size-6 text-gold"/>
        <div><h1 className="font-display text-2xl font-bold text-gold"><T k="Oponentes"/></h1>
          <p className="text-sm text-muted"><T k="Deck do adversário e recompensas da ISO ativa"/></p></div></div>
    </div>
    <div className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-56 flex-1 flex-col gap-1 text-xs text-muted">Oponente
          <select className="field px-3 py-2 text-sm" value={selected}
            onChange={e=>{setSelected(Number(e.target.value));setShowDrops(false);setPreview(null)}}>
            {!result?.opponents?.length&&<option value={0}><T k="Nenhum oponente"/></option>}
            {(result?.opponents??[]).map(o=><option key={o.id} value={o.id}>#{o.id} {o.name}</option>)}
          </select>
        </label>
        <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-muted">Buscar carta no deck
          <div className="field flex items-center gap-2 px-3 py-2"><Search className="size-4 text-primary"/>
            <input className="min-w-0 w-full bg-transparent outline-none" value={query}
              onChange={e=>setQuery(e.target.value)} placeholder={t("Nome, ID ou tipo")}/></div>
        </label>
        <button type="button" className="btn-ghost" onClick={()=>setRefresh(v=>v+1)}><RefreshCcw className="size-4"/><T k="Atualizar"/></button>
        <button type="button" disabled={!result?.opponentId} className="btn-gold disabled:opacity-50"
          onClick={()=>setShowDrops(v=>!v)}><Gift className="size-4"/> {showDrops?"Ocultar drops":"Ver drops"}
          <ChevronDown className={"size-4 "+(showDrops?"rotate-180":"")}/></button>
      </div>
      {error&&<p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {loading&&<p className="mt-3 text-sm text-muted"><T k="Lendo a tabela do oponente…"/></p>}
      {result&&<p className="mt-3 text-sm text-muted">{result.status}</p>}
      {result?.provisional&&<p className="mt-2 text-xs text-gold"><T k="Atenção: a lista representa a posição estrutural do pool nesta ISO. O nome do oponente ainda não foi confirmado por testes em duelo."/></p>}
      {result?.available&&<div className="mt-3 flex flex-wrap gap-2 text-sm text-primary">
        <span>{result.cards.length} tipos de cartas possíveis</span>
        <span>· Pool com {result.totalWeight.toLocaleString("pt-BR")} pontos de peso</span>
      </div>}
      {result?.available&&<div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map(card=><button type="button" key={card.id}
          onClick={()=>selectCard(card.id)}
          className="flex min-w-0 gap-3 rounded-xl border border-line/70 bg-[#0b1b34]/80 p-3 text-left hover:border-primary/60">
          <CardFace sha={sha} id={card.id} name={card.name} width="w-20"/>
          <div className="min-w-0">
            <p className="text-xs text-gold">#{card.id}</p>
            <p className="font-semibold text-white">{card.name}</p>
            <p className="mt-1 text-xs text-muted">{card.type}</p>
            <p className="mt-2 text-xs text-primary">Peso: {card.weight}</p>
            {card.chancePercent!==null&&<p className="text-xs text-muted">{card.chancePercent.toLocaleString("pt-BR")}% do pool</p>}
          </div>
        </button>)}
      </div>}
      {result?.available&&rows.length===0&&<p className="mt-4 text-sm text-muted"><T k="Nenhuma carta encontrada."/></p>}
    </div>
    {showDrops&&<div className="panel rounded-xl p-4">
      <h2 className="mb-2 font-display text-lg font-semibold text-gold"><T k="Drops do oponente"/></h2>
      <p className="text-xs text-muted"><T k="Recompensas exibidas somente quando o scanner possui dados associados ao oponente."/></p>
      {!drops&&!dropsError&&<p className="mt-3 text-sm text-muted"><T k="Consultando drops…"/></p>}
      {dropsError&&<p role="alert" className="mt-3 text-sm text-red-300">{dropsError}</p>}
      {drops&&<p className="mt-3 text-xs text-muted">{drops.status}</p>}
      {drops?.provisional&&<p className="mt-2 text-xs text-gold"><T k="DROPS CANDIDATOS · correspondência nome/ID e grupos de RANK ainda sem validação em duelo."/></p>}
      {drops&&!drops.rows.length&&<p className="mt-3 text-sm text-muted"><T k="Nenhum drop publicado para este oponente com a evidência disponível."/></p>}
      {drops?.rows?.map((row,i)=><div key={i} className="mt-2 flex gap-3 rounded-lg border border-line/70 p-2">
        <button type="button" className="min-w-0 flex-1 text-left"
          onClick={()=>selectCard(row.cardId)}>
          <span className="text-xs text-gold">#{row.cardId} · {row.groupLabel}</span>
          <p className="font-semibold text-white">{row.cardName}</p>
        </button>
        <span className="shrink-0 text-sm text-primary">{row.chancePercent.toLocaleString("pt-BR",{maximumFractionDigits:4})}%</span>
      </div>)}
      {(drops?.total??0)>100&&<p className="mt-2 text-xs text-muted"><T k="Exibindo os primeiros 100 drops. Veja a aba Drops para a lista completa."/></p>}
    </div>}
    <CardHoverPreview selection={preview} sha={sha} cards={cards} onClose={()=>setPreview(null)}/>
  </section>
}
