"use client"

import Image from "next/image"
import {createPortal} from "react-dom"
import {useEffect,useMemo,useRef,useState} from "react"
import {ArrowLeft,BookOpen,Layers,X} from "lucide-react"
import {cardClassicHd,cardArtHd,cardArt,desktopApi} from "@/lib/desktop"
import type {CardDropSources,CardFusionPaths,DropRow,LocalCard} from "@/lib/desktop"

/** Click-only selection. No hover timer, mouse-leave or focus popup. */
export type CardPreviewSelection = {
  card:LocalCard
  fallbackDrop?:DropRow
}

function EnlargedArtwork({card,sha}:{card:LocalCard;sha:string|null}) {
  const [source,setSource]=useState<"classic"|"hd"|"original"|"none">("classic")
  useEffect(()=>setSource("classic"),[sha,card.id])
  const url=source==="classic"?cardClassicHd(sha,card.id):
    source==="hd"?cardArtHd(sha,card.id):
    source==="original"?cardArt(sha,card.id):null
  const ratio=source==="classic"?"aspect-[9/13]":"aspect-[17/16]"
  return <div className={"relative mx-auto w-full max-w-64 overflow-hidden rounded-lg border border-gold/45 bg-[#061126] shadow-[0_0_24px_rgb(56_200_255/0.14)] "+ratio}>
    {url?<Image src={url} alt={"Carta "+card.name} fill unoptimized sizes="256px"
      className="object-contain"
      onError={()=>setSource(old=>old==="classic"?"hd":old==="hd"?"original":"none")}/>:
      <div className="flex h-full items-center justify-center">
        <Layers className="size-12 text-primary/45" aria-label="Arte indisponível"/>
      </div>}
  </div>
}

/** Card details shared by Library, Fusions and Drops.
 * Click a recommendation to navigate within this one stable dialog.
 * The back stack belongs to this dialog; no extra windows are spawned.
 */
export function CardHoverPreview({selection,sha,cards,onClose}:{
  selection:CardPreviewSelection|null
  sha:string|null
  cards:LocalCard[]
  onClose:()=>void
}) {
  const [mounted,setMounted]=useState(false)
  const [history,setHistory]=useState<LocalCard[]>([])
  const [fusions,setFusions]=useState<CardFusionPaths|null>(null)
  const [fusionError,setFusionError]=useState(false)
  const [drops,setDrops]=useState<CardDropSources|null>(null)
  const [dropError,setDropError]=useState(false)
  const closeButton=useRef<HTMLButtonElement>(null)
  const dialogRef=useRef<HTMLDivElement>(null)
  const cardById=useMemo(()=>new Map(cards.map(card=>[card.id,card])),[cards])

  useEffect(()=>setMounted(true),[])
  useEffect(()=>{
    setHistory(selection?[selection.card]:[])
  },[selection,sha])
  const card=history.length?history[history.length-1]:null
  const cardId=card?.id??null

  useEffect(()=>{
    setFusions(null)
    setFusionError(false)
    if(!sha||cardId===null||!selection)return
    const api=desktopApi()
    if(!api){setFusionError(true);return}
    let active=true
    void api.get_card_fusion_paths(cardId).then(data=>{
      if(!active)return
      if(data.romSha===sha&&data.cardId===cardId)setFusions(data)
      else setFusionError(true)
    }).catch(()=>{if(active)setFusionError(true)})
    return()=>{active=false}
  },[sha,cardId,selection])

  useEffect(()=>{
    setDrops(null)
    setDropError(false)
    if(!sha||cardId===null||!selection)return
    const api=desktopApi()
    if(!api){setDropError(true);return}
    let active=true
    void api.get_card_drop_sources(cardId).then(data=>{
      if(!active)return
      if(data.romSha===sha&&data.cardId===cardId)setDrops(data)
      else setDropError(true)
    }).catch(()=>{if(active)setDropError(true)})
    return()=>{active=false}
  },[sha,cardId,selection])

  useEffect(()=>{
    if(!selection)return
    const previouslyFocused=document.activeElement instanceof HTMLElement
      ?document.activeElement:null
    const oldOverflow=document.body.style.overflow
    document.body.style.overflow="hidden"
    closeButton.current?.focus()
    const onKey=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();onClose();return}
      if(event.key==="Backspace"&&event.altKey) {
        event.preventDefault()
        setHistory(old=>old.length>1?old.slice(0,-1):old)
        return
      }
      if(event.key!=="Tab"||!dialogRef.current)return
      const controls=Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]),select:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])'))
      if(!controls.length)return
      const first=controls[0],last=controls[controls.length-1]
      if(event.shiftKey&&document.activeElement===first){
        event.preventDefault();last.focus()
      }else if(!event.shiftKey&&document.activeElement===last){
        event.preventDefault();first.focus()
      }
    }
    document.addEventListener("keydown",onKey)
    return()=>{
      document.removeEventListener("keydown",onKey)
      document.body.style.overflow=oldOverflow
      previouslyFocused?.focus()
    }
  },[selection,onClose])

  const navigate=(id:number,name:string)=>{
    if(!Number.isInteger(id)||id<1||id>722)return
    const destination=cardById.get(id)??{
      id,name,type:"",category:"Não identificada",attribute:"",
      atk:null,def:null,effect:null,effectSource:null,
    }
    setHistory(previous=>{
      if(previous[previous.length-1]?.id===id)return previous
      // Bounded history avoids huge navigation stacks on cyclic recipes.
      return [...previous.slice(-19),destination]
    })
    dialogRef.current?.scrollTo({top:0,behavior:"instant"})
  }
  const back=()=>setHistory(previous=>
    previous.length>1?previous.slice(0,-1):previous)

  if(!mounted||!selection||!card)return null
  const matchedFusions=fusions?.romSha===sha&&fusions.cardId===card.id
  const materialRows=matchedFusions?fusions.materialRows.slice(0,5):[]
  const resultRows=matchedFusions?fusions.resultRows.slice(0,5):[]
  const matchedDrops=drops?.romSha===sha&&drops.cardId===card.id&&drops.available
  const dropRows=matchedDrops?drops.rows.slice(0,4):
    !drops&&!dropError&&card.id===selection.card.id&&selection.fallbackDrop
      ?[selection.fallbackDrop]:[]
  const description=card.descriptionSource&&card.description?.trim()
    ?card.description.trim():null
  const effect=card.effectSource&&card.effect?.trim()
    ?card.effect.trim():null
  const duplicateText=Boolean(description&&effect&&description===effect)

  const cardLink=(id:number,name:string)=>{
    return <button type="button" onClick={()=>navigate(id,name)}
      className="rounded px-0.5 font-semibold text-gold underline-offset-2 hover:text-white hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      aria-label={"Abrir informações de "+name}>
      {name} <span className="text-[10px] text-muted">#{id}</span>
    </button>
  }

  return createPortal(
    <div className="fixed inset-0 z-[9997] flex items-center justify-center bg-[#020713]/80 p-2 backdrop-blur-sm sm:p-4"
      onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
      <div ref={dialogRef} role="dialog" aria-modal="true"
        aria-label={"Informações e fusões de "+card.name}
        className="dueltrace-scroll max-h-[calc(100dvh-16px)] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gold/50 bg-[#08172e] p-3 shadow-[0_25px_85px_rgb(0_0_0/0.85)] sm:max-h-[calc(100dvh-32px)] sm:p-5">
        <header className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {history.length>1&&<button type="button" onClick={back}
              aria-label="Voltar para a carta anterior"
              className="flex items-center gap-1 rounded-md border border-primary/30 px-2 py-1.5 text-xs text-primary hover:bg-primary/10">
              <ArrowLeft className="size-4"/>Voltar
            </button>}
            <span className="text-xs font-semibold text-gold">DUELTRACE · Detalhes da carta</span>
          </div>
          <button ref={closeButton} type="button" onClick={onClose}
            aria-label="Fechar informações da carta"
            className="rounded-lg p-1.5 text-muted hover:bg-primary/10 hover:text-white">
            <X className="size-5"/>
          </button>
        </header>
        <div className="grid gap-4 sm:grid-cols-[210px_minmax(0,1fr)]">
          <div className="min-w-0">
            <EnlargedArtwork card={card} sha={sha}/>
            <p className="mt-2 text-center text-[11px] text-muted">
              Arte extraída do mod selecionado
            </p>
          </div>
          <div className="min-w-0">
            <span className="text-xs font-bold text-gold">#{card.id}</span>
            <h2 className="mt-1 break-words font-display text-xl font-bold text-white">
              {card.name}
            </h2>
            {(card.type||card.attribute)&&<p className="mt-2 text-sm text-muted">
              {[card.type,card.attribute].filter(Boolean).join(" · ")}
            </p>}
            <div className="mt-3 flex flex-wrap gap-2 text-sm font-semibold tabular-nums">
              <span className="rounded-lg border border-primary/45 bg-primary/10 px-3 py-1.5 text-primary">
                ATK {card.atk??"—"}
              </span>
              <span className="rounded-lg border border-gold/45 bg-gold/10 px-3 py-1.5 text-gold">
                DEF {card.def??"—"}
              </span>
            </div>
            <div className="mt-3 border-t border-line/70 pt-3 text-xs leading-relaxed">
              {description||effect?<div className="space-y-2">
                {description&&<div>
                  <h3 className="font-semibold text-gold">
                    {duplicateText?"Descrição / efeito":"Descrição"}
                  </h3>
                  <p className="whitespace-pre-line break-words text-foreground/85">{description}</p>
                </div>}
                {effect&&!duplicateText&&<div>
                  <h3 className="font-semibold text-gold">Efeito</h3>
                  <p className="whitespace-pre-line break-words text-foreground/85">{effect}</p>
                </div>}
              </div>:<p className="text-muted">
                Descrição e efeito não disponíveis para esta carta.
              </p>}
            </div>
          </div>
        </div>
        <section className="mt-4 border-t border-line/70 pt-3">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-primary">
            <BookOpen className="size-4"/>Fusões usando esta carta como material
          </h3>
          {materialRows.length?<ul className="space-y-1.5">
            {materialRows.map(row=><li key={row.partnerId+"-"+row.resultId}
              className="rounded-lg border border-line/60 bg-panel-strong/60 px-3 py-2 text-xs">
              <span className="text-muted">+ </span>
              {cardLink(row.partnerId,row.partnerName)}
              <span className="mx-2 text-primary">→</span>
              {cardLink(row.resultId,row.resultName)}
              <span className="ml-2 text-primary">ATK {row.atk??"—"} · DEF {row.def??"—"}</span>
            </li>)}
          </ul>:<p className="text-xs text-muted">
            {fusionError?"Não foi possível consultar fusões deste mod.":
              matchedFusions?"Nenhuma fusão cadastrada com esta carta como material.":
              "Consultando fusões…"}
          </p>}
          {matchedFusions&&fusions.materialTotal>5&&<p className="mt-2 text-[11px] text-muted">
            Mostrando 5 de {fusions.materialTotal} possibilidades.
          </p>}
        </section>
        <section className="mt-4 border-t border-line/70 pt-3">
          <h3 className="mb-2 text-sm font-bold text-primary">
            Fusões que resultam nesta carta
          </h3>
          {resultRows.length?<ul className="space-y-1.5">
            {resultRows.map(row=><li key={row.materialAId+"-"+row.materialBId}
              className="rounded-lg border border-line/60 bg-panel-strong/60 px-3 py-2 text-xs">
              {cardLink(row.materialAId,row.materialAName)}
              <span className="mx-2 text-muted">+</span>
              {cardLink(row.materialBId,row.materialBName)}
              <span className="mx-2 text-primary">→</span>
              <span className="font-semibold text-white">{card.name}</span>
            </li>)}
          </ul>:<p className="text-xs text-muted">
            {fusionError?"Não foi possível consultar fusões deste mod.":
              matchedFusions?"Nenhuma receita cadastrada que produza esta carta.":
              "Consultando fusões…"}
          </p>}
          {matchedFusions&&fusions.resultTotal>5&&<p className="mt-2 text-[11px] text-muted">
            Mostrando 5 de {fusions.resultTotal} receitas.
          </p>}
          {matchedFusions&&fusions.provisional&&<p className="mt-2 text-[11px] text-gold/80">
            Algumas receitas são candidatas estruturais da ISO, ainda não confirmadas em duelo.
          </p>}
        </section>
        <section className="mt-4 border-t border-line/70 pt-3">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-primary">
            Onde conseguir
          </h3>
          {dropRows.length?<ul className="space-y-1.5">
            {dropRows.map(row=><li key={row.opponentId+"-"+row.group}
              className="flex items-start justify-between gap-3 text-xs">
              <div className="min-w-0">
                <p className="truncate font-semibold text-white">{row.opponentName}</p>
                <p className="text-[11px] text-muted">{row.eligibleRanks.join(" / ")}</p>
              </div>
              <span className="shrink-0 font-semibold text-gold">
                {row.chancePercent.toLocaleString("pt-BR",{maximumFractionDigits:3})}%
              </span>
            </li>)}
          </ul>:<p className="text-xs text-muted">
            {dropError || (drops && !drops.available)
              ?"Drops indisponíveis neste mod.":matchedDrops
                ?"Nenhum drop registrado para esta carta.":"Consultando drops…"}
          </p>}
        </section>
        <p className="mt-3 text-[11px] text-muted">
          Clique nos nomes das cartas para explorar outras combinações. Use Voltar para retornar ou Esc para fechar.
        </p>
      </div>
    </div>,document.body)
}
