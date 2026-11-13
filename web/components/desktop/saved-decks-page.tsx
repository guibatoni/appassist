"use client"

import {useEffect,useMemo,useState} from "react"
import Link from "next/link"
import {BookMarked,Layers,Search,RefreshCcw,ArrowLeft} from "lucide-react"
import {desktopApi} from "@/lib/desktop"
import type {DeckLibrary,LocalCard} from "@/lib/desktop"
import {CardFace} from "./deck-card-face"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"
import {DeckFusionGallery} from "./deck-fusion-gallery"

const normalize=(value:string)=>value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("pt-BR").trim()

/** Named snapshots live in DUELTRACE_DATA, never overwrite PS1 Memory Cards.
 * Loadouts are read-only build references: viewing does not send a deck to ePSXe.
 */
export function SavedDecksPage({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const [index,setIndex]=useState<DeckLibrary|null>(null)
  const [detail,setDetail]=useState<DeckLibrary|null>(null)
  const [selectedId,setSelectedId]=useState("")
  const [search,setSearch]=useState("")
  const [cardSearch,setCardSearch]=useState("")
  const [refresh,setRefresh]=useState(0)
  const [error,setError]=useState("")
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const byId=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])

  useEffect(()=>{
    const requested=new URLSearchParams(window.location.search).get("deck")
    setSelectedId(requested&&requested.length<=90?requested:"")
    setIndex(null);setDetail(null);setSearch("");setCardSearch("");setPreview(null);setError("")
  },[sha])

  useEffect(()=>{
    let active=true,reading=false
    const api=desktopApi()
    if(!api||!sha){setIndex(null);return}
    const load=async()=>{
      if(reading)return
      reading=true
      try{
        const next=await api.get_deck_library()
        if(active){setIndex(next);setError("")}
      }catch(e){
        if(active)setError(e instanceof Error?e.message:"Não foi possível consultar os decks salvos.")
      }finally{reading=false}
    }
    void load()
    const timer=window.setInterval(()=>void load(),12000)
    return()=>{active=false;window.clearInterval(timer)}
  },[sha,refresh])

  useEffect(()=>{
    if(!index)return
    const saved=index.saved??[]
    if(!saved.length){setSelectedId("");setDetail(null);return}
    if(!saved.some(item=>item.id===selectedId))setSelectedId(saved[0].id)
  },[index,selectedId])

  useEffect(()=>{
    let active=true,reading=false
    const api=desktopApi()
    if(!api||!sha||!selectedId){setDetail(null);return}
    setDetail(null)
    const load=async()=>{
      if(reading)return
      reading=true
      try{
        const next=await api.get_deck_library(selectedId)
        if(active){setDetail(next);setError("")}
      }catch(e){
        if(active){setDetail(null);setError(e instanceof Error?e.message:"Loadout indisponível.")}
      }finally{reading=false}
    }
    void load()
    const timer=window.setInterval(()=>void load(),12000)
    return()=>{active=false;window.clearInterval(timer)}
  },[sha,selectedId,refresh])

  const matching=useMemo(()=>{
    const query=normalize(search)
    return (index?.saved??[]).filter(entry=>{
      if(!query)return true
      if(normalize(entry.name).includes(query))return true
      return entry.ids.some(id=>normalize((byId.get(id)?.name??"")+" #"+id).includes(query))
    })
  },[index,search,byId])
  const selected=index?.saved.find(item=>item.id===selectedId)
  const shownCards=useMemo(()=>{
    const query=normalize(cardSearch)
    return (detail?.cards??[]).filter(card=>!query||normalize(card.name+" #"+card.id).includes(query))
  },[detail,cardSearch])

  const showCard=(id:number)=>{
    const card=byId.get(id)
    if(card)setPreview({card})
  }

  return <section className="flex flex-col gap-4">
    <header className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <BookMarked className="size-7 text-gold"/>
          <div>
            <h1 className="font-display text-2xl font-semibold text-gold">Decks Salvos</h1>
            <p className="text-sm text-muted">Seus loadouts para consultar, comparar e montar no jogo</p>
          </div>
        </div>
        <Link href="/decks" className="btn-ghost"><ArrowLeft className="size-4"/> Deck atual</Link>
      </div>
    </header>

    {error&&<p className="rounded-lg border border-red-500/50 bg-red-950/30 p-3 text-sm text-red-200" role="alert">{error}</p>}
    {!sha&&<p className="panel rounded-xl p-4 text-sm text-muted">Ative uma ISO na Biblioteca de Mods para consultar os loadouts dessa versão do jogo.</p>}
    {sha&&<div className="grid items-start gap-4 xl:grid-cols-[minmax(270px,0.38fr)_minmax(0,1fr)]">
      <section className="panel min-w-0 rounded-xl p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-semibold text-gold">Meus loadouts</h2>
          <button className="btn-ghost" type="button" onClick={()=>setRefresh(n=>n+1)} title="Recarregar decks salvos">
            <RefreshCcw className="size-4"/> Atualizar
          </button>
        </div>
        <p className="mt-1 text-xs text-muted">{index?.saved.length??0} decks salvos ou capturas automáticas para a ISO ativa</p>
        <label className="mt-3 flex flex-col gap-1 text-xs text-muted">
          Pesquisar loadout ou carta incluída
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted"/>
            <input className="field w-full py-2 pl-9 pr-3 text-sm"
              value={search} onChange={e=>setSearch(e.target.value)}
              placeholder="Nome do deck ou de uma carta"
              aria-label="Pesquisar decks salvos"/>
          </div>
        </label>
        <div className="mt-3 max-h-[620px] space-y-2 overflow-y-auto pr-1">
          {matching.map(item=>{
            const names=new Set(item.ids)
            return <button type="button" key={item.id} onClick={()=>{setSelectedId(item.id);setCardSearch("");setPreview(null)}}
              aria-pressed={selectedId===item.id}
              className={"w-full rounded-lg border p-3 text-left transition-colors "+
                (selectedId===item.id?"border-gold bg-gold/10":"border-line/50 bg-[#09172d] hover:border-primary/60")}>
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 break-words font-semibold text-white">{item.name}</span>
                <span className="shrink-0 text-xs text-primary">40 cartas</span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {item.source==="memory_card"?"Captura automática":"Loadout salvo manualmente"} · {names.size} cartas diferentes
              </p>
              {item.createdAt&&<p className="mt-1 text-[11px] text-muted">
                {new Date(item.createdAt).toLocaleDateString("pt-BR")}
              </p>}
            </button>
          })}
          {index&&!matching.length&&<p className="rounded-lg border border-line/50 p-3 text-sm text-muted">
            {index.saved.length?"Nenhum deck contém o nome pesquisado.":"Ainda não há decks salvos para esta ISO. Vá à aba Decks e escolha Salvar deck."}
          </p>}
          {!index&&!error&&<p className="text-sm text-muted">Consultando loadouts…</p>}
        </div>
      </section>

      <div className="min-w-0 space-y-4">
        {detail&&selected?
        <>
          <section className="panel rounded-xl p-4">
            <h2 className="font-display text-xl font-semibold text-gold">{selected.name}</h2>
            <p className="mt-1 text-sm text-muted">
              Loadout de referência · {detail.deckCount}/40 cartas · {detail.cards.length} cartas diferentes
            </p>
            <p className="mt-1 text-xs text-muted">
              Esta visualização não altera o deck do ePSXe ou os arquivos de Memory Card.
              Para montar, use a relação de cartas abaixo como referência.
            </p>
            <label className="mt-3 flex flex-col gap-1 text-xs text-muted">
              Localizar carta neste loadout
              <input className="field w-full px-3 py-2 text-sm" value={cardSearch}
                onChange={e=>setCardSearch(e.target.value)}
                placeholder="Nome ou ID da carta" aria-label="Pesquisar carta do loadout"/>
            </label>
            <p className="mt-2 text-xs text-primary">
              {shownCards.length} de {detail.cards.length} cartas diferentes na lista
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {shownCards.map(card=><button type="button" key={card.id} onClick={()=>showCard(card.id)}
                className="flex min-w-0 gap-3 rounded-lg border border-line/60 bg-[#0b1b34] p-3 text-left hover:border-primary/60">
                <CardFace sha={sha} id={card.id} name={card.name} width="w-16"/>
                <div className="min-w-0">
                  <p className="text-xs text-gold">#{card.id} · {card.count}×</p>
                  <p className="break-words text-sm font-semibold text-white">{card.name}</p>
                  <p className="mt-2 text-xs text-muted">ATK {card.atk??"—"} · DEF {card.def??"—"}</p>
                </div>
              </button>)}
            </div>
            {shownCards.length===0&&<p className="mt-3 text-sm text-muted">Nenhuma carta encontrada neste deck.</p>}
          </section>
          <DeckFusionGallery state={detail} sha={sha} onCardClick={showCard}/>
        </>:
        <section className="panel rounded-xl p-4 text-sm text-muted">
          {index?.saved.length?"Selecione um loadout para ver as 40 cartas e as fusões possíveis.":"Salve seu deck atual na aba Decks para começar a montar sua coleção de loadouts."}
        </section>}
      </div>
    </div>}
    <CardHoverPreview selection={preview} sha={sha} cards={cards} onClose={()=>setPreview(null)}/>
  </section>
}
