"use client"

import {T,useI18n} from "@/lib/i18n"

import {useEffect,useMemo,useState} from "react"
import Link from "next/link"
import {useRouter} from "next/navigation"
import {BookMarked,Layers,RefreshCcw,Save,FolderOpen,Search} from "lucide-react"
import {desktopApi} from "@/lib/desktop"
import type {DeckLibrary,LocalCard} from "@/lib/desktop"
import {CardFace} from "./deck-card-face"
import {DeckFusionGallery} from "./deck-fusion-gallery"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"

export function DecksPage({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const {t}=useI18n()
  const router=useRouter()
  const [cardQuery,setCardQuery]=useState("")
  const [state,setState]=useState<DeckLibrary|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState("")
  const [name,setName]=useState("")
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const [refresh,setRefresh]=useState(0)
  const byId=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const filteredCards=useMemo(()=>{
    const q=cardQuery.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("pt-BR").trim()
    return (state?.cards??[]).filter(card=>!q||
      (card.name+" #"+card.id).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("pt-BR").includes(q))
  },[state,cardQuery])

  useEffect(()=>{setCardQuery("");setState(null);setPreview(null);setError("")},[sha])
  useEffect(()=>{
    let active=true
    const api=desktopApi()
    if(!api||!sha){setState(null);return}
    const load=async()=>{
      try{
        const result=await api.get_deck_library()
        if(active){setState(result);setError("")}
      }catch(e){
        if(active){setError(e instanceof Error?e.message:"Não foi possível ler o deck.")}
      }
    }
    void load()
    const poll=window.setInterval(()=>void load(),6000)
    return()=>{active=false;window.clearInterval(poll)}
  },[sha,refresh])

  const chooseSave=async(block:number)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true)
    try{
      await api.select_memory_save(block)
      setRefresh(v=>v+1)
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível selecionar o save.")}
    finally{setBusy(false)}
  }

  const chooseMemoryCard=async()=>{
    const api=desktopApi()
    if(!api||busy)return
    setBusy(true)
    try{
      const response=await api.select_memory_card()
      if(!response.cancelled){setPreview(null);setRefresh(v=>v+1);setError("")}
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível selecionar o Memory Card.")}
    finally{setBusy(false)}
  }

  const saveDeck=async()=>{
    const api=desktopApi()
    if(!api||!name.trim())return
    setBusy(true)
    try{
      const response=await api.save_current_deck(name.trim())
      if(response.saved){
        setName("")
        router.push("/decks-salvos"+(response.id?"?deck="+encodeURIComponent(response.id):""))
      }
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível salvar.")}
    finally{setBusy(false)}
  }
  const showCard=(id:number)=>{
    const card=byId.get(id)
    if(card)setPreview({card})
  }
  return <section className="flex flex-col gap-4">
    <header className="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] p-4">
      <div className="flex items-center gap-3"><Layers className="size-6 text-gold"/>
        <div><h1 className="font-display text-2xl font-bold text-gold"><T k="Decks"/></h1>
          <p className="text-sm text-muted">Deck atual do Memory Card, pesquisa de cartas e fusões possíveis</p></div>
        <Link href="/decks-salvos" className="btn-ghost ml-auto"><BookMarked className="size-4"/> Meus Decks</Link>
      </div>
    </header>
    <div className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-white">{state?.cardName??"Memory Card não selecionado"}</p>
          <p className="text-sm text-muted">{state?.status??"Abra a Biblioteca de Mods para selecionar o Memory Card."}</p>
          {state?.saveDisplayName&&<p className="text-xs text-primary">
            Save selecionado: {state.saveDisplayName}
          </p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" disabled={busy||!desktopApi()}
            onClick={()=>void chooseMemoryCard()}>
            <FolderOpen className="size-4"/> Selecionar outro Memory Card
          </button>
          <button type="button" className="btn-ghost" onClick={()=>setRefresh(x=>x+1)}>
            <RefreshCcw className="size-4"/> Recarregar
          </button>
        </div>
      </div>
      {error&&<p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      <p className="mt-2 text-xs text-muted">
        As cartas abaixo vêm do Memory Card selecionado ou de um snapshot local, e não de um endereço RAM estimado.
        {state?.liveDeckStatus?" "+state.liveDeckStatus:""}
      </p>
      <p className="mt-3 text-xs text-muted"><T k="O DUELTRACE identifica o título do save PS1 quando disponível e associa cada bloco ao mod que você selecionou. Mods que compartilham o mesmo identificador do jogo não podem ser diferenciados só por esse código. O ePSXe continua responsável pelo cartão original."/></p>
      {(state?.saves?.length??0)>0&&
        <label className="mt-4 flex flex-col gap-1 text-sm text-muted">Saves identificados neste Memory Card
          <select className="field max-w-xl px-3 py-2" value={state?.selectedBlock??""}
            disabled={busy}
            onChange={e=>{if(e.target.value)void chooseSave(Number(e.target.value))}}>
            <option value=""><T k="Escolha o save correto"/></option>
            {state!.saves.map(save=><option key={save.block} value={save.block}>
              {save.displayName}
            </option>)}
          </select>
        </label>}
      {(state?.blocks?.length??0)>0&&
        <div className="mt-4" aria-label="15 blocos físicos do Memory Card">
          <p className="mb-2 text-sm font-semibold text-white">
            Blocos do Memory Card ({state?.saves?.length??0} saves FM íntegros de 15 posições físicas)
          </p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
            {state!.blocks!.map(slot=><button type="button" key={slot.block}
              disabled={busy||!slot.selectable}
              onClick={()=>void chooseSave(slot.block)}
              title={`Bloco ${slot.block}: ${slot.label}`}
              aria-label={`Bloco ${slot.block}: ${slot.label}`}
              aria-pressed={state?.selectedBlock===slot.block}
              className={"min-h-16 rounded-lg border p-2 text-left text-xs "+
                (state?.selectedBlock===slot.block?"border-gold bg-gold/10 text-gold":
                slot.selectable?"border-primary/50 bg-primary/10 text-white hover:border-gold":
                "border-line/50 bg-background/30 text-muted cursor-default")}>
                <span className="block font-semibold">Bloco {slot.block}</span>
                <span className="mt-1 block text-[11px]">{slot.label}</span>
              </button>)}
          </div>
          <p className="mt-2 text-xs text-muted">
            Um cartão PS1 possui 15 blocos de dados, mas nem todos são partidas salvas.
            Apenas saves de Forbidden Memories com integridade confirmada podem ser escolhidos.
            O ePSXe pode usar dois cartões diferentes; selecione o arquivo do outro cartão se o seu save não aparecer.
          </p>
        </div>}
      {state?.savePinned&&state.selectedBlock&&
        <p className="mt-2 text-xs text-primary">Bloco {state.selectedBlock} salvo como preferência desta ISO. A sequência acompanha os saves do jogo.</p>}
      <p className="mt-3 text-xs text-muted">
        Salve uma cópia nomeada do deck e consulte-a depois em <Link href="/decks-salvos" className="text-primary underline">Meus Decks</Link>.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input className="field min-w-52 flex-1 px-3 py-2 text-sm"
          aria-label={t("Nome do novo deck salvo")} placeholder={t("Nome para salvar o deck ativo")}
          value={name} maxLength={72} onChange={e=>setName(e.target.value)}/>
        <button type="button" className="btn-gold disabled:opacity-50"
          disabled={busy||state?.deckCount!==40||!state?.saveName||!name.trim()||!desktopApi()}
          onClick={()=>void saveDeck()}><Save className="size-4"/> <T k="Salvar deck"/></button>
      </div>
    </div>
    <div className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-gold">
          <BookMarked className="size-5"/> {state?.displayName??"Deck gravado"}
        </h2>
        <p className="text-sm text-primary">{state?.deckCount??0}/40 cartas</p>
      </div>
      {state?.deckCount===40&&<p className="mt-2 text-xs text-primary">
        Origem: {state.deckSource==="snapshot"?"cópia local escolhida":"save selecionado do Memory Card"}.
        Integridade do formato do save verificada, sem garantia de que seja o deck ativo nesta partida.
      </p>}
      {state?.deckCount===40&&<div className="mt-3">
        <label className="flex flex-col gap-1 text-xs text-muted">
          Buscar carta no deck pelo nome ou ID
          <span className="relative block">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted"/>
            <input className="field w-full py-2 pl-9 pr-3 text-sm"
              value={cardQuery} onChange={e=>setCardQuery(e.target.value)}
              placeholder="Digite o nome da carta..." aria-label="Pesquisar carta no deck"/>
          </span>
        </label>
        <p className="mt-2 text-xs text-primary">
          {filteredCards.length} de {state.cards.length} cartas diferentes · 40 cartas no deck
        </p>
      </div>}
      {state?.deckCount===40?
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {filteredCards.map(card=><button type="button" key={card.id} onClick={()=>showCard(card.id)}
          className="flex min-w-0 gap-3 rounded-lg border border-line/60 bg-[#0b1b34] p-3 text-left hover:border-primary/60">
          <CardFace sha={sha} id={card.id} name={card.name} width="w-20"/>
          <div className="min-w-0"><p className="text-xs text-gold">#{card.id} · {card.count}×</p>
            <p className="font-semibold text-white">{card.name}</p>
            <p className="mt-2 text-xs text-muted">ATK {card.atk??"—"} · DEF {card.def??"—"}</p>
          </div>
        </button>)}
      </div>:
      <p className="mt-3 text-sm text-muted"><T k="Nenhum deck foi aprovado nas verificações de integridade deste save. Se houver vários saves no cartão, selecione a partida correta."/></p>}
      {state?.deckCount===40&&filteredCards.length===0&&
        <p className="mt-3 text-sm text-muted">Nenhuma carta corresponde à pesquisa. Tente outro nome.</p>}
    </div>
    <DeckFusionGallery state={state} sha={sha} onCardClick={showCard}/>
    <CardHoverPreview selection={preview} sha={sha} cards={cards} onClose={()=>setPreview(null)}/>
  </section>
}
