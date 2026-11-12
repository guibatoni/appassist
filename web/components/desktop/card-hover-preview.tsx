"use client"

import Image from "next/image"
import {createPortal} from "react-dom"
import {useEffect,useState} from "react"
import {ChevronLeft,ChevronRight,Layers,X} from "lucide-react"
import {cardArt,cardWithFrame,desktopApi} from "@/lib/desktop"
import type {CardDropSources,CardFusionSuggestions,DropRow,LocalCard} from "@/lib/desktop"

export type CardPreviewSelection = {
  card:LocalCard
  anchor:HTMLElement
  fallbackDrop?:DropRow
  pinned?:boolean
}

// A prévia e o fundo escurecido só aparecem após um segundo de permanência.
const CARD_PREVIEW_DELAY_MS=1000

function EnlargedArtwork({card,sha}:{card:LocalCard;sha:string|null}) {
  const [source,setSource]=useState<"frame"|"art"|"none">("frame")
  useEffect(()=>setSource("frame"),[sha,card.id])
  const url=source==="frame"?cardWithFrame(sha,card.id):
    source==="art"?cardArt(sha,card.id):null
  return <div className="relative mx-auto aspect-[52/60] w-full max-w-48 overflow-hidden rounded border border-gold/40 bg-[#061126] shadow-[0_0_24px_rgb(56_200_255/0.18)]">
    {url?<Image src={url} alt={card.name} fill unoptimized sizes="192px"
      className={source==="frame"?"object-fill [image-rendering:pixelated]":"object-contain [image-rendering:pixelated]"}
      onError={()=>setSource(source==="frame"?"art":"none")}/>:
      <div className="flex h-full items-center justify-center"><Layers className="size-12 text-primary/45" aria-label="Arte indisponível"/></div>}
  </div>
}

/**
 * Prévia única de Biblioteca, Fusões e Drops, centralizada na janela.
 * O escurecimento e a janela não interceptam o mouse, preservando o hover
 * sobre a carta original e o atraso de um segundo sem piscadas.
 */
export function CardHoverPreview({selection,sha,onClose}:{
  selection:CardPreviewSelection|null;sha:string|null;onClose:()=>void
}) {
  const [mounted,setMounted]=useState(false)
  const [revealed,setRevealed]=useState<CardPreviewSelection|null>(null)
  const [result,setResult]=useState<CardDropSources|null>(null)
  const [error,setError]=useState(false)
  const [fusions,setFusions]=useState<CardFusionSuggestions|null>(null)
  const [fusionError,setFusionError]=useState(false)
  const [fusionSort,setFusionSort]=useState<"atk"|"name"|"id">("atk")
  const [fusionPage,setFusionPage]=useState(0)
  // Um novo hover/foco inicia a contagem; sair da carta cancela o timer.
  // A identidade da seleção impede que uma prévia anterior pisque na tela.
  useEffect(()=>{
    setRevealed(null)
    if(!selection)return
    if(selection.pinned){
      if(selection.anchor.isConnected)setRevealed(selection)
      return
    }
    const timer=window.setTimeout(()=>{
      if(selection.anchor.isConnected)setRevealed(selection)
    },CARD_PREVIEW_DELAY_MS)
    return()=>window.clearTimeout(timer)
  },[selection])

  const activeSelection=selection&&revealed===selection?revealed:null
  const card=activeSelection?.card??null
  const cardId=card?.id??null

  useEffect(()=>setMounted(true),[])

  useEffect(()=>{setFusionSort("atk");setFusionPage(0)},[sha,cardId])

  // Requests are tied to the selected ISO and card ID: never reuse data from
  // another mod, and do not infer fusions from the names of the cards.
  useEffect(()=>{
    setFusions(null)
    setFusionError(false)
    if(!sha||cardId===null)return
    const api=desktopApi()
    if(!api)return
    let active=true
    void api.get_card_fusions(cardId,fusionPage*8,8,fusionSort).then(data=>{
      if(!active)return
      if(data.romSha===sha&&data.cardId===cardId)setFusions(data)
      else setFusionError(true)
    }).catch(()=>{if(active)setFusionError(true)})
    return()=>{active=false}
  },[sha,cardId,fusionPage,fusionSort])

  useEffect(()=>{
    setResult(null)
    setError(false)
    if(!sha||cardId===null)return
    const api=desktopApi()
    if(!api)return
    let active=true
    const timer=window.setTimeout(()=>{
      void api.get_card_drop_sources(cardId).then(data=>{
        if(!active)return
        if(data.cardId===cardId&&data.romSha===sha)setResult(data)
        else setError(true)
      }).catch(()=>{if(active)setError(true)})
    },140)
    return()=>{active=false;window.clearTimeout(timer)}
  },[sha,cardId])

  useEffect(()=>{
    if(!selection)return
    const escape=(event:KeyboardEvent)=>{
      if(event.key==="Escape")onClose()
    }
    document.addEventListener("keydown",escape)
    return()=>document.removeEventListener("keydown",escape)
  },[selection,onClose])

  if(!mounted||!activeSelection||!card)return null
  const matched=result?.romSha===sha&&result.cardId===card.id
  const matchedFusions=fusions?.romSha===sha&&fusions.cardId===card.id
  const fusionRows=matchedFusions?fusions.rows:[]
  const fusionTotal=matchedFusions?fusions.total:0
  const fusionPages=Math.max(1,Math.ceil(fusionTotal/8))
  const rows=matched&&result.available?result.rows:[]
  const dropRows=rows.length?rows.slice(0,4):
    !result&&!error&&activeSelection.fallbackDrop?[activeSelection.fallbackDrop]:[]
  const more=Math.max(0,rows.length-dropRows.length)
  // Apenas textos com procedência no perfil selecionado são apresentados.
  const description=card.descriptionSource&&card.description?.trim()?card.description.trim():null
  const effect=card.effectSource&&card.effect?.trim()?card.effect.trim():null
  const duplicateText=Boolean(description&&effect&&description===effect)

  return createPortal(<>
    <div aria-hidden="true" onClick={activeSelection.pinned?onClose:undefined}
      className={(activeSelection.pinned?"pointer-events-auto ":"pointer-events-none ")+"fixed inset-0 z-[90] bg-[#020713]/75 backdrop-blur-[2px]"}/>
    <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center p-3">
      <div role={activeSelection.pinned?"dialog":"tooltip"} aria-modal={activeSelection.pinned?true:undefined}
        aria-label={activeSelection.pinned?`Informações de ${card.name}`:undefined}
        id={"card-preview-"+card.id}
        className={(activeSelection.pinned?"pointer-events-auto ":"pointer-events-none ")+"dueltrace-scroll max-h-[calc(100dvh-24px)] w-[min(calc(100vw-24px),500px)] overflow-y-auto rounded-2xl border border-gold/55 bg-[#08172e]/98 p-3 sm:p-4 shadow-[0_25px_85px_rgb(0_0_0/0.85)] backdrop-blur-xl transition-[opacity,transform] duration-200 scale-100 opacity-100"}>
      {activeSelection.pinned&&<button type="button" aria-label="Fechar informações da carta"
        onClick={onClose} className="mb-2 ml-auto flex rounded-md p-1 text-muted hover:bg-primary/10 hover:text-white">
        <X className="size-5"/>
      </button>}
      <div className="flex flex-col items-center gap-3 min-[480px]:flex-row min-[480px]:items-start min-[480px]:gap-4">
        <div className="w-32 shrink-0 min-[480px]:w-40 sm:w-48">
          <EnlargedArtwork card={card} sha={sha}/>
        </div>
        <div className="min-w-0 w-full flex-1">
          <span className="text-xs font-bold text-gold">#{card.id}</span>
          <h3 className="mt-1 break-words font-display text-lg font-bold text-white">{card.name}</h3>
          {(card.type||card.attribute)&&<p className="mt-2 text-xs text-muted">
            {[card.type,card.attribute].filter(Boolean).join(" · ")}
          </p>}
          {card.category==="Monstros"&&<p className="mt-3 text-sm font-semibold tabular-nums text-primary">
            ATK {card.atk??"—"} · DEF {card.def??"—"}
          </p>}
        </div>
      </div>
      <div className="mt-3 border-t border-line/70 pt-3">
        {description||effect?<div className="space-y-2">
          {description&&<div>
            <h4 className="mb-1 text-xs font-semibold text-gold">
              {duplicateText?"Descrição / efeito":"Descrição"}
            </h4>
            <p className="whitespace-pre-line break-words line-clamp-4 text-xs leading-relaxed text-foreground/85">{description}</p>
          </div>}
          {effect&&!duplicateText&&<div>
            <h4 className="mb-1 text-xs font-semibold text-gold">Efeito</h4>
            <p className="whitespace-pre-line break-words line-clamp-4 text-xs leading-relaxed text-foreground/85">{effect}</p>
          </div>}
        </div>:<p className="text-xs text-muted">Descrição e efeito não disponíveis para esta carta.</p>}
      </div>
      <div className="mt-3 border-t border-line/70 pt-3">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-primary">Onde conseguir</h4>
        {dropRows.length?<>
          <div className="space-y-1.5">
            {dropRows.map(row=><div key={row.opponentId+"-"+row.group}
              className="flex items-start justify-between gap-3 text-xs">
              <div className="min-w-0">
                <p className="truncate font-semibold text-white">{row.opponentName}</p>
                <p className="text-[11px] text-muted">{row.eligibleRanks.join(" / ")}</p>
              </div>
              <span className="shrink-0 font-semibold tabular-nums text-gold">
                {row.chancePercent.toLocaleString("pt-BR",{maximumFractionDigits:3})}%
              </span>
            </div>)}
          </div>
          {more>0&&<p className="mt-2 text-[11px] text-muted">+{more} outras possibilidades</p>}
        </>:<p className="text-xs text-muted">
          {matched&&result?.available?"Nenhum drop registrado para esta carta.":
            result||error?"Drops não disponíveis neste mod.":"Consultando drops…"}
        </p>}
      </div>
      <div className="mt-3 border-t border-line/70 pt-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-primary">Possíveis fusões</h4>
          {activeSelection.pinned&&<select value={fusionSort} aria-label="Ordenar fusões possíveis"
            onChange={event=>{setFusionSort(event.target.value as "atk"|"name"|"id");setFusionPage(0)}}
            className="field max-w-full px-2 py-1 text-xs">
            <option value="atk">Maior ATK</option><option value="name">Resultado A–Z</option>
            <option value="id">ID do resultado</option>
          </select>}
        </div>
        {fusionRows.length?<>
          <ul className="space-y-1.5">
            {fusionRows.map(fusion=><li key={fusion.partnerId+"-"+fusion.resultId}
              className="rounded-lg border border-line/50 bg-panel-strong/60 px-2.5 py-2 text-xs">
              <p className="break-words text-foreground/80">
                + #{fusion.partnerId} <span className="font-semibold text-white">{fusion.partnerName}</span>
              </p>
              <div className="mt-1 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                <p className="min-w-0 break-words font-semibold text-gold">
                  → #{fusion.resultId} {fusion.resultName}
                </p>
                <span className="shrink-0 font-semibold tabular-nums text-primary">
                  ATK {fusion.atk??"—"}
                </span>
              </div>
            </li>)}
          </ul>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] text-muted">{fusionTotal} combinação(ões) nesta ISO</span>
            {activeSelection.pinned&&fusionPages>1&&<div className="flex items-center gap-1">
              <button type="button" aria-label="Fusões anteriores"
                disabled={fusionPage===0} onClick={()=>setFusionPage(x=>Math.max(0,x-1))}
                className="rounded-md p-1 text-primary disabled:opacity-30"><ChevronLeft className="size-4"/></button>
              <span className="text-[11px] tabular-nums text-muted">{fusionPage+1}/{fusionPages}</span>
              <button type="button" aria-label="Mais fusões"
                disabled={fusionPage+1>=fusionPages} onClick={()=>setFusionPage(x=>x+1)}
                className="rounded-md p-1 text-primary disabled:opacity-30"><ChevronRight className="size-4"/></button>
            </div>}
            {!activeSelection.pinned&&fusionTotal>fusionRows.length&&
              <span className="text-[11px] text-muted">Clique na carta para ver outras combinações.</span>}
          </div>
          {fusions?.provisional&&<p className="mt-2 text-[11px] text-muted">
            Algumas combinações são candidatas extraídas da ISO, ainda não confirmadas em duelo.
          </p>}
        </>:<p className="text-xs text-muted">{fusionError?"Fusões indisponíveis neste mod.":
          matchedFusions?"Nenhuma fusão encontrada com esta carta como material.":
          "Consultando fusões da ISO ativa…"}</p>}
      </div>
      <p className="mt-3 text-[11px] text-muted">
        {activeSelection.pinned?"Clique fora da janela ou pressione Esc para fechar.":
          "Afaste o mouse ou pressione Esc para fechar. Clique na carta para explorar as fusões."}
      </p>
      </div>
    </div>
  </>,document.body)
}
