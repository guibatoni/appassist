"use client"

import {useEffect,useMemo,useState} from "react"
import {BookMarked,Layers,RefreshCcw,Save} from "lucide-react"
import {desktopApi} from "@/lib/desktop"
import type {DeckLibrary,LocalCard} from "@/lib/desktop"
import {CardFace} from "./deck-card-face"
import {CardHoverPreview} from "./card-hover-preview"
import type {CardPreviewSelection} from "./card-hover-preview"

export function DecksPage({sha,cards}:{sha:string|null;cards:LocalCard[]}) {
  const [chosen,setChosen]=useState("")
  const [state,setState]=useState<DeckLibrary|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState("")
  const [name,setName]=useState("")
  const [preview,setPreview]=useState<CardPreviewSelection|null>(null)
  const [refresh,setRefresh]=useState(0)
  const byId=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])

  useEffect(()=>{setChosen("");setState(null);setPreview(null);setError("")},[sha])
  useEffect(()=>{
    let active=true
    const api=desktopApi()
    if(!api||!sha){setState(null);return}
    const load=async()=>{
      try{
        const result=await api.get_deck_library(chosen)
        if(active){setState(result);setError("")}
      }catch(e){
        if(active){setError(e instanceof Error?e.message:"Não foi possível ler o deck.")}
      }
    }
    void load()
    const poll=window.setInterval(()=>void load(),6000)
    return()=>{active=false;window.clearInterval(poll)}
  },[sha,chosen,refresh])

  const chooseSave=async(block:number)=>{
    const api=desktopApi()
    if(!api)return
    setBusy(true)
    try{
      await api.select_memory_save(block)
      setChosen("")
      setRefresh(v=>v+1)
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível selecionar o save.")}
    finally{setBusy(false)}
  }

  const saveDeck=async()=>{
    const api=desktopApi()
    if(!api||!name.trim())return
    setBusy(true)
    try{
      const response=await api.save_current_deck(name.trim())
      if(response.saved){setName("");setRefresh(x=>x+1)}
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
        <div><h1 className="font-display text-2xl font-bold text-gold">Decks</h1>
          <p className="text-sm text-muted">Deck gravado no Memory Card, decks salvos e fusões possíveis</p></div>
      </div>
    </header>
    <div className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-white">{state?.cardName??"Memory Card não selecionado"}</p>
          <p className="text-sm text-muted">{state?.status??"Abra a Biblioteca de Mods para selecionar o Memory Card."}</p>
          {state?.saveName&&<p className="text-xs text-primary">Save: {state.saveName}</p>}
        </div>
        <button type="button" className="btn-ghost" onClick={()=>setRefresh(x=>x+1)}>
          <RefreshCcw className="size-4"/> Recarregar
        </button>
      </div>
      {error&&<p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      <p className="mt-3 text-xs text-muted">O DUELTRACE valida as verificações internas do save e acompanha alterações no arquivo. O cartão pode conter um deck salvo diferente do deck atualmente carregado no ePSXe. A seleção de ISO não confirma automaticamente qual save o emulador abriu.</p>
      {(state?.saves?.length??0)>1&&
        <label className="mt-4 flex flex-col gap-1 text-sm text-muted">Selecionar partida salva no cartão
          <select className="field max-w-xl px-3 py-2" value={state?.selectedBlock??""}
            disabled={busy}
            onChange={e=>{if(e.target.value)void chooseSave(Number(e.target.value))}}>
            <option value="">Escolha o save correto</option>
            {state!.saves.map(save=><option key={save.block} value={save.block}>
              Bloco {save.block} · {save.saveName} · sequência {save.saveSequence}
            </option>)}
          </select>
        </label>}
      <label className="mt-4 flex flex-col gap-1 text-sm text-muted">Selecionar deck
        <select value={chosen} onChange={e=>{setChosen(e.target.value);setPreview(null)}}
          className="field max-w-xl px-3 py-2 text-sm">
          <option value="">Deck gravado no Memory Card</option>
          {(state?.saved??[]).map(item=>
            <option key={item.id} value={item.id}>{item.name} · {item.source==="memory_card"?"Automático":"Salvo"}</option>)}
        </select>
      </label>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input className="field min-w-52 flex-1 px-3 py-2 text-sm"
          aria-label="Nome do novo deck salvo" placeholder="Nome para salvar o deck ativo"
          value={name} maxLength={72} onChange={e=>setName(e.target.value)}/>
        <button type="button" className="btn-gold disabled:opacity-50"
          disabled={busy||!state?.linked||!state?.saveName||!name.trim()||!desktopApi()}
          onClick={()=>void saveDeck()}><Save className="size-4"/> Salvar deck</button>
      </div>
    </div>
    <div className="panel rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-gold">
          <BookMarked className="size-5"/> {state?.displayName??"Deck gravado"}
        </h2>
        <p className="text-sm text-primary">{state?.deckCount??0}/40 cartas</p>
      </div>
      {state?.deckCount===40?
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {state.cards.map(card=><button type="button" key={card.id} onClick={()=>showCard(card.id)}
          className="flex min-w-0 gap-3 rounded-lg border border-line/60 bg-[#0b1b34] p-3 text-left hover:border-primary/60">
          <CardFace sha={sha} id={card.id} name={card.name} width="w-20"/>
          <div className="min-w-0"><p className="text-xs text-gold">#{card.id} · {card.count}×</p>
            <p className="font-semibold text-white">{card.name}</p>
            <p className="mt-2 text-xs text-muted">ATK {card.atk??"—"} · DEF {card.def??"—"}</p>
          </div>
        </button>)}
      </div>:
      <p className="mt-3 text-sm text-muted">Nenhum deck foi aprovado nas verificações de integridade deste save. Se houver vários saves no cartão, selecione a partida correta.</p>}
    </div>
    <div className="panel rounded-xl p-4">
      <h2 className="font-display text-lg font-semibold text-gold">Fusões possíveis com este deck</h2>
      <p className="mt-1 text-xs text-muted">Combinações calculadas com as receitas disponíveis do mod ativo. Não representam garantia de fusão em duelo.</p>
      {state?.fusions.provisional&&<p className="mt-2 text-xs text-gold">Inclui receitas candidatas da ISO ainda não confirmadas durante uma partida.</p>}
      <p className="mt-2 text-sm text-primary">{state?.fusions.total??0} resultados encontrados</p>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {(state?.fusions.rows??[]).map((f,i)=><div key={i}
          className="rounded-lg border border-line/60 bg-[#09172d] p-3">
          <p className="text-sm text-white"><span className="text-primary">{f.nameA}</span> + <span className="text-primary">{f.nameB}</span></p>
          <button className="mt-1 text-left text-sm font-semibold text-gold hover:underline"
            onClick={()=>showCard(f.result)} type="button">= {f.nameResult} #{f.result}</button>
          <p className="mt-1 text-[11px] text-muted">{f.source}</p>
        </div>)}
      </div>
      {(state?.fusions.total??0)>80&&<p className="mt-2 text-xs text-muted">Exibindo os primeiros 80 resultados.</p>}
    </div>
    <CardHoverPreview selection={preview} sha={sha} cards={cards} onClose={()=>setPreview(null)}/>
  </section>
}
