"use client"

import Image from "next/image"
import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, FilePlus2, Gamepad2,
  GitMerge, Layers, Play, RefreshCcw, Search, Shield, Swords, Upload,
} from "lucide-react"
import {cardArt, desktopApi, sourceLabel, useDesktopState} from "@/lib/desktop"
import type {LocalCard, HandState, FusionPage, LocalMod, RankState} from "@/lib/desktop"

type Page = "inicio" | "mods" | "biblioteca" | "fusoes"

function Heading({title,subtitle}:{title:string;subtitle:string}) {
  return <div className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-5 py-4">
    <h1 className="font-display text-2xl font-bold text-gold sm:text-3xl">{title}</h1>
    <p className="mt-1 text-sm text-muted">{subtitle}</p>
  </div>
}

type FramePalettes = Record<string,{accent:string;source:string;wa_offset:number}>
function frameAccent(card:LocalCard|null, palettes:FramePalettes):string|undefined {
  if(!card)return undefined
  const key=card.category==="Mágicas"?"magia":card.category==="Armadilhas"?"armadilha":
    card.category==="Rituais"?"ritual":card.category==="Equipamentos"?"magia":"normal"
  const color=palettes[key]?.accent
  return typeof color==="string"&&/^#[0-9a-fA-F]{6}$/.test(color)?color:undefined
}
function CardThumbnail({card,sha,palettes={}}:{
  card:LocalCard|null;sha:string|null;palettes?:FramePalettes
}) {
  const [broken,setBroken]=useState(false)
  const url=card?cardArt(sha,card.id):null
  const accent=frameAccent(card,palettes)
  return <div style={accent?{borderColor:accent,boxShadow:"0 0 15px "+accent+"55"}:undefined}
    className="relative mx-auto flex aspect-[3/4] w-full max-w-32 items-center justify-center overflow-hidden rounded-lg border-2 border-gold/50 bg-gradient-to-b from-[#19466d] via-[#102449] to-[#060e23] p-2 shadow-[0_0_18px_rgb(56_200_255/0.18)]">
    {url&&!broken?<Image src={url} alt={card?.name??""} fill unoptimized sizes="160px" className="object-contain" onError={()=>setBroken(true)}/>:
      <Layers className="size-9 text-primary/45" aria-label="Imagem não extraída"/>}
    {card&&<span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[10px] text-gold">#{card.id}</span>}
  </div>
}

function Empty({children}:{children:React.ReactNode}) {
  return <p className="rounded-lg border border-line/60 bg-[#06152c]/70 px-4 py-6 text-center text-sm text-muted">{children}</p>
}

function RankPanel({sha}:{sha:string|null}) {
  const [rank,setRank]=useState<RankState|null>(null)
  const [lp,setLp]=useState("")
  const [busy,setBusy]=useState(false)
  useEffect(()=>{
    let mounted=true,busyRead=false
    setRank(null)
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
  return <section className="panel rounded-xl p-4" aria-label="Contador de RANK">
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
      {rank?.ready&&<span className="text-xs text-gold">Estimativa · não é resultado final</span>}
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
        {[["Turnos",rank.counters.turns],["Fusões",rank.counters.fusions],
          ["Magias",rank.counters.spells],["LP",rank.counters.remaining_lp]].map(([label,value])=>
          <div key={label} className="rounded-md border border-line/50 bg-background/40 px-3 py-2">
            <span className="block">{label}</span><strong className="font-display text-base text-white">{value??"—"}</strong>
          </div>)}
      </div>}
    <p className="mt-3 text-xs text-muted">
      A contagem só é habilitada para o modelo Remaster X15 de SHA conhecido, após confirmação dos LP.
      A origem do endereço no ePSXe ainda é experimental. Outros mods exigem análise própria.
    </p>
  </section>
}

function Home({sha,palettes}:{sha:string|null;palettes:FramePalettes}) {
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
            <CardThumbnail key={String(sha)+"-"+String(card?.id??"empty")} card={card} sha={sha} palettes={palettes}/>
            <p className="mt-2 min-h-9 text-center text-xs font-semibold text-white">{card?.name??"Aguardando carta"}</p>
            <p className="text-center text-[11px] text-primary">ATK {card?.atk??"—"} · DEF {card?.def??"—"}</p>
          </div>
        })}
      </div>
    </div>
    <div className="panel rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl text-gold">Fusões disponíveis</h2>
        <div className="flex gap-2">
          <button type="button" onClick={()=>setMode("pairs")} className={mode==="pairs"?"btn-gold":"btn-ghost"}>Duplas</button>
          <button type="button" onClick={()=>setMode("chains")} className={mode==="chains"?"btn-gold":"btn-ghost"}>Cadeias (3–5)</button>
        </div>
      </div>
      {!hand?.ready?<Empty>Entre em duelo no ePSXe. Nenhuma mão fictícia é exibida.</Empty>:
        mode==="pairs"?(hand.pairs.length?<div className="grid gap-2 lg:grid-cols-2">
          {hand.pairs.map((x,i)=><div key={i} className="rounded-lg border border-line/70 bg-panel-strong/60 p-3">
            <p className="text-xs text-primary">Slots {x.slot_a} + {x.slot_b}</p>
            <p className="mt-1 font-semibold text-white">{x.result_name} #{x.result}</p>
            <p className="mt-1 text-xs text-gold">ATK {x.atk??"—"} · {sourceLabel(x.validation)}</p>
          </div>)}</div>:<Empty>Não há fusões de duas cartas para a mão atual.</Empty>):
        (hand.chains.length?<div className="grid gap-3 lg:grid-cols-2">
          {hand.chains.map((x,i)=><div key={i} className="rounded-xl border border-gold/30 bg-gradient-to-r from-[#112746] to-panel p-3">
            <p className="font-semibold text-gold">{x.result_name} #{x.result} · ATK {x.atk??"—"}</p>
            <p className="mt-1 text-xs text-primary">Ordem: {x.slot_order.join(" → ")}</p>
            <ol className="mt-2 space-y-1 text-xs text-muted">{x.steps.map((s,j)=>
              <li key={j}>{j+1}. #{s.material_a} + #{s.material_b} = #{s.result} ({sourceLabel(s.validation)})</li>)}</ol>
          </div>)}</div>:<Empty>Nenhuma cadeia de 3 a 5 cartas foi identificada.</Empty>)}
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
        <button type="button" className="btn-ghost" onClick={()=>void onRefresh()}>
          <RefreshCcw className="size-4"/> Atualizar</button>
      </div>
      {message&&<p className="mt-3 text-sm text-gold" role="status">{message}</p>}
      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {mods.map(mod=><div key={mod.sha256} className={"rounded-xl border bg-gradient-to-b from-panel-strong/90 to-panel/50 p-4 "+(sha===mod.sha256?"border-success/70":"border-line/70")}>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0">
            <p className="truncate font-semibold text-white">{mod.name}</p>
            <p className="mt-1 text-xs text-muted">{mod.sha256.slice(0,18)}…</p>
          </div><span className={sha===mod.sha256?"text-xs text-success":"text-xs text-gold"}>{sha===mod.sha256?"Ativo":mod.requiresReview?"Revisão necessária":"Conhecido"}</span></div>
          <div className="my-4 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
            {([["Cartas",mod.cards],["Descrições",mod.descriptions??0],["Fusões",mod.fusions],["Efeitos",mod.effects]] as const).map(([label,n])=>
              <div key={label} className="rounded-lg border border-line/50 bg-background/70 p-2"><p className="font-display text-xl text-primary">{n}</p><p className="text-xs text-muted">{label}</p></div>)}
          </div>
          <button type="button" disabled={busy||!desktopApi()}
            className="btn-ghost mb-2 w-full disabled:opacity-40"
            onClick={()=>void run(
              ()=>desktopApi()!.reanalyze_mod(mod.sha256),
              "Arquivos SLUS e WA_MRG reanalisados e vinculados à ISO."
            )}>
            <RefreshCcw className="size-4"/> Reanalisar arte, descrições e molduras
          </button>
        <button type="button" disabled={busy||!desktopApi()||sha===mod.sha256}
            className="btn-gold w-full disabled:opacity-40" onClick={()=>{
              const ok=!mod.requiresReview||window.confirm("O mod requer revisão. Ativar somente os dados comprovados?")
              if(ok)void run(()=>desktopApi()!.activate_mod(mod.sha256,mod.requiresReview),"Perfil ativado.")
            }}>{sha===mod.sha256?"Perfil ativo":"Ativar perfil"}</button>
        </div>)}
      </div>
      {!mods.length&&<Empty>Nenhum mod cadastrado. Importe uma ISO/BIN na versão Windows. Os arquivos não são enviados ao Vercel.</Empty>}
    </section>
  </>
}

function Library({cards,sha,palettes}:{cards:LocalCard[];sha:string|null;palettes:FramePalettes}) {
  const [search,setSearch]=useState("")
  const [sort,setSort]=useState<"id"|"atk"|"name">("id")
  const [page,setPage]=useState(0)
  const [selectedId,setSelectedId]=useState<number|null>(null)
  const visible=useMemo(()=>{
    const q=search.trim().toLowerCase()
    const filtered=cards.filter(c=>!q||(String(c.id)+" "+c.name+" "+c.type+" "+c.category).toLowerCase().includes(q))
    filtered.sort((a,b)=>sort==="atk"?(b.atk??-1)-(a.atk??-1):sort==="name"?a.name.localeCompare(b.name,"pt-BR"):a.id-b.id)
    return filtered
  },[cards,search,sort])
  const chosen=cards.find(c=>c.id===selectedId)??visible[0]??null
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
          <option value="id">ID</option><option value="atk">Maior ATK</option><option value="name">Nome</option>
        </select>
        <span className="self-center text-sm text-muted">{visible.length} / {cards.length} cartas</span>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {visible.slice(page*32,(page+1)*32).map(card=><button type="button" key={card.id}
              className={"rounded-lg border p-2 text-center transition hover:border-primary "+(chosen?.id===card.id?"border-primary bg-primary/10":"border-line/70 bg-panel-strong/60")}
              onClick={()=>setSelectedId(card.id)}>
              <CardThumbnail key={String(sha)+"-"+card.id} card={card} sha={sha} palettes={palettes}/>
              <p className="mt-2 min-h-9 text-xs font-semibold text-white">{card.name}</p>
              <p className="text-[11px] text-primary">ATK {card.atk??"—"} · DEF {card.def??"—"}</p>
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
            <div className="my-4"><CardThumbnail key={String(sha)+"-"+chosen.id} card={chosen} sha={sha} palettes={palettes}/></div>
            <p className="text-sm text-primary">ATK {chosen.atk??"—"} · DEF {chosen.def??"—"}</p>
            <p className="mt-2 text-sm text-muted">Tipo: {chosen.type||"Não identificado"}</p>
            <p className="text-sm text-muted">Categoria: {chosen.category}</p>
            {chosen.category==="Monstros"&&
              <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-line/60 bg-background/60 p-3 text-xs text-muted">
                <p>Nível: <strong className="text-white">{chosen.level??"—"}</strong></p>
                <p>Atributo: <strong className="text-white">{chosen.attributeId==null?"—":"Código "+chosen.attributeId}</strong></p>
                <p>Estrela 1: <strong className="text-white">{chosen.guardianStar1==null?"—":"Código "+chosen.guardianStar1}</strong></p>
                <p>Estrela 2: <strong className="text-white">{chosen.guardianStar2==null?"—":"Código "+chosen.guardianStar2}</strong></p>
              </div>}
            <div className="mt-4 rounded-lg border border-gold/30 bg-background/60 p-3">
              <h3 className="mb-1 font-semibold text-gold">Descrição da carta</h3>
              <p className="whitespace-pre-line text-sm text-foreground/85">
                {chosen.description??"Descrição ainda não reconhecida no SLUS desta ISO."}
              </p>
              {chosen.descriptionSource&&<p className="mt-2 text-xs text-muted">Origem: {chosen.descriptionSource}</p>}
            </div>
            <div className="mt-4 rounded-lg border border-line/70 bg-background/60 p-3">
              <h3 className="mb-1 font-semibold text-primary">Efeito com fonte</h3>
              <p className="text-sm text-foreground/85">{chosen.effect??"Efeito não identificado de forma verificável."}</p>
              {chosen.effectSource&&<p className="mt-2 text-xs text-gold">Fonte: {chosen.effectSource}</p>}
              {!chosen.effect&&chosen.effectHint&&
                <div className="mt-3 rounded-lg border border-gold/30 bg-gold/5 p-2">
                  <p className="text-xs font-semibold text-gold">Possível efeito citado na descrição</p>
                  <p className="mt-1 whitespace-pre-line text-xs text-foreground/85">{chosen.effectHint}</p>
                  <p className="mt-1 text-xs text-muted">
                    Texto do SLUS; efeito ainda não confirmado no jogo.
                  </p>
                </div>}
            </div></>:<Empty>Selecione uma carta.</Empty>}
        </aside>
      </div>
    </section>
  </>
}

function FusionIllustration({id,name,sha,card,role,palettes}:{
  id:number;name:string;sha:string|null;card:LocalCard|null;role:string;palettes:FramePalettes
}) {
  const displayed:LocalCard=card??{
    id,name,type:"",attribute:"",category:"Não identificada",
    atk:null,def:null,effect:null,effectSource:null
  }
  return <div className="flex min-w-0 flex-col items-center gap-1.5" title={name}>
    <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{role}</span>
    <div className="w-16 sm:w-20">
      <CardThumbnail key={String(sha)+"-"+id} card={displayed} sha={sha} palettes={palettes}/>
    </div>
    <span className="text-center text-[11px] font-semibold text-gold">#{id}</span>
    <span className="line-clamp-2 min-h-8 break-words text-center text-xs font-medium text-foreground">{name}</span>
    <span className="text-center text-[11px] font-semibold tabular-nums text-primary">
      ATK {card?.atk??"—"} · DEF {card?.def??"—"}
    </span>
  </div>
}

function Fusions({sha,cards,palettes}:{sha:string|null;cards:LocalCard[];palettes:FramePalettes}) {
  const [query,setQuery]=useState("")
  const [offset,setOffset]=useState(0)
  const [records,setRecords]=useState<FusionPage|null>(null)
  const [error,setError]=useState<string|null>(null)
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const pageSize=12
  useEffect(()=>{
    let mounted=true
    setRecords(null)
    const id=window.setTimeout(async()=>{
      const api=desktopApi()
      if(!api){if(mounted)setRecords(null);return}
      try{
        const result=await api.get_fusions(query,offset,pageSize)
        if(mounted){setRecords(result);setError(null)}
      }catch(e){if(mounted)setError(e instanceof Error?e.message:"Falha ao carregar fusões")}
    },220)
    return()=>{mounted=false;window.clearTimeout(id)}
  },[sha,query,offset])
  return <>
    <Heading title="Biblioteca de Fusões" subtitle="Imagem, nome e ID de cada material e resultado — somente receitas do mod ativo"/>
    <section className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="field flex min-w-56 flex-1 items-center gap-2 px-3 py-2">
          <Search className="size-4 text-primary"/>
          <input className="w-full bg-transparent outline-none" placeholder="Pesquisar material, resultado ou ID"
            value={query} onChange={e=>{setQuery(e.target.value);setOffset(0)}}/>
        </label>
        <span className="text-xs text-muted">{records?.total??0} receitas</span>
      </div>
      {error&&<p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {records?.rows.map((r,i)=><article key={r.a+"-"+r.b+"-"+r.result+"-"+i}
          className="rounded-xl border border-line/80 bg-gradient-to-br from-panel-strong/90 via-[#0b1a35] to-background p-3 shadow-[inset_0_1px_0_rgb(245_184_61/0.09)] transition-colors hover:border-primary/60">
          <div className="grid grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)] items-start gap-1">
            <FusionIllustration id={r.a} name={r.nameA} card={cardsById.get(r.a)??null} sha={sha} role="Material A" palettes={palettes}/>
            <span className="pt-14 text-center font-display text-xl font-bold text-primary" aria-hidden>+</span>
            <FusionIllustration id={r.b} name={r.nameB} card={cardsById.get(r.b)??null} sha={sha} role="Material B" palettes={palettes}/>
            <span className="pt-14 text-center font-display text-xl font-bold text-gold" aria-hidden>→</span>
            <FusionIllustration id={r.result} name={r.nameResult} card={cardsById.get(r.result)??null} sha={sha} role="Resultado" palettes={palettes}/>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line/50 pt-2">
            <span className="text-xs text-muted">{sourceLabel(r.source)}</span>
            <span className="text-sm font-semibold tabular-nums text-primary">ATK {r.atk??"—"}</span>
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
      <span className={state?.connected?"flex items-center gap-2 text-success":"flex items-center gap-2 text-gold"}>
        {state?.connected?<CheckCircle2 className="size-4"/>:<AlertTriangle className="size-4"/>}
        {state?.connected?"Motor Python conectado":"Prévia do v0 — sem acesso ao ePSXe"}
      </span>
      <span className="text-muted">Mod ativo: <strong className="font-semibold text-white">{state?.activeName??"Nenhum"}</strong></span>
    </div>
    {error&&<p className="rounded-lg border border-gold/40 bg-gold/10 p-3 text-sm text-gold" role="status">{error}</p>}
    {loading&&<p className="text-sm text-muted">Carregando dados locais...</p>}
    {page==="inicio"&&<Home sha={state?.activeSha??null} palettes={state?.framePalettes??{}}/>}
    {page==="mods"&&<Mods mods={state?.mods??[]} sha={state?.activeSha??null} configured={Boolean(state?.epsxeConfigured)} onRefresh={refresh}/>}
    {page==="biblioteca"&&<Library sha={state?.activeSha??null} cards={state?.cards??[]} palettes={state?.framePalettes??{}}/>}
    {page==="fusoes"&&<Fusions sha={state?.activeSha??null} cards={state?.cards??[]} palettes={state?.framePalettes??{}}/>}
  </div>
}
