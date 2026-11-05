"use client"

import Image from "next/image"
import {createPortal} from "react-dom"
import {useEffect,useRef,useState} from "react"
import {Layers} from "lucide-react"
import {cardArt,cardWithFrame,desktopApi} from "@/lib/desktop"
import type {CardDropSources,DropRow,LocalCard} from "@/lib/desktop"

export type CardPreviewSelection = {
  card:LocalCard
  anchor:HTMLElement
  fallbackDrop?:DropRow
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
 * Prévia única de Fusões e Drops. O painel fica CENTRALIZADO sobre a carta
 * de origem, com limites da viewport. O escurecimento não intercepta o mouse:
 * um hover sobre o botão original permanece estável, sem piscadas.
 */
export function CardHoverPreview({selection,sha,onClose}:{
  selection:CardPreviewSelection|null;sha:string|null;onClose:()=>void
}) {
  const panelRef=useRef<HTMLDivElement|null>(null)
  const [mounted,setMounted]=useState(false)
  const [revealed,setRevealed]=useState<CardPreviewSelection|null>(null)
  const [position,setPosition]=useState<{left:number;top:number}|null>(null)
  const [result,setResult]=useState<CardDropSources|null>(null)
  const [error,setError]=useState(false)
  // Um novo hover/foco inicia a contagem; sair da carta cancela o timer.
  // A identidade da seleção impede que uma prévia anterior pisque na tela.
  useEffect(()=>{
    setRevealed(null)
    setPosition(null)
    if(!selection)return
    const timer=window.setTimeout(()=>{
      if(selection.anchor.isConnected)setRevealed(selection)
    },CARD_PREVIEW_DELAY_MS)
    return()=>window.clearTimeout(timer)
  },[selection])

  const activeSelection=selection&&revealed===selection?revealed:null
  const card=activeSelection?.card??null
  const cardId=card?.id??null

  useEffect(()=>setMounted(true),[])

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

  // Painel ancorado no CENTRO do item; adapta-se ao espaço disponível.
  useEffect(()=>{
    if(!activeSelection||!mounted){
      setPosition(null)
      return
    }
    const place=()=>{
      const anchor=activeSelection.anchor
      const panel=panelRef.current
      if(!anchor.isConnected||!panel)return
      const rect=anchor.getBoundingClientRect()
      const width=panel.offsetWidth
      const height=panel.offsetHeight
      const margin=12
      const centerX=rect.left+rect.width/2
      const centerY=rect.top+rect.height/2
      const left=Math.max(margin,Math.min(centerX-width/2,window.innerWidth-width-margin))
      const top=Math.max(margin,Math.min(centerY-height/2,window.innerHeight-height-margin))
      setPosition({left,top})
    }
    const frame=window.requestAnimationFrame(place)
    window.addEventListener("resize",place)
    window.addEventListener("scroll",place,true)
    const observer=typeof ResizeObserver==="undefined"?null:new ResizeObserver(place)
    if(panelRef.current)observer?.observe(panelRef.current)
    return()=>{
      window.cancelAnimationFrame(frame)
      window.removeEventListener("resize",place)
      window.removeEventListener("scroll",place,true)
      observer?.disconnect()
    }
  },[activeSelection,mounted,result,error])

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
  const rows=matched&&result.available?result.rows:[]
  const dropRows=rows.length?rows.slice(0,4):
    !result&&!error&&activeSelection.fallbackDrop?[activeSelection.fallbackDrop]:[]
  const more=Math.max(0,rows.length-dropRows.length)

  return createPortal(<>
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-[90] bg-[#020713]/75 backdrop-blur-[2px]"/>
    <div ref={panelRef} role="tooltip" id={"card-preview-"+card.id}
      style={position??{left:0,top:0}}
      className={"pointer-events-none fixed z-[100] max-h-[calc(100vh-24px)] w-[min(94vw,500px)] overflow-hidden rounded-2xl border border-gold/55 bg-[#08172e]/98 p-4 shadow-[0_25px_85px_rgb(0_0_0/0.85)] backdrop-blur-xl transition-[opacity,transform] duration-200 "+
        (position?"scale-100 opacity-100":"scale-95 opacity-0")}>
      <div className="flex items-start gap-4">
        <div className="w-40 shrink-0 sm:w-48">
          <EnlargedArtwork card={card} sha={sha}/>
        </div>
        <div className="min-w-0 flex-1">
          <span className="text-xs font-bold text-gold">#{card.id}</span>
          <h3 className="mt-1 break-words font-display text-lg font-bold text-white">{card.name}</h3>
          {(card.type||card.attribute)&&<p className="mt-2 text-xs text-muted">
            {[card.type,card.attribute].filter(Boolean).join(" · ")}
          </p>}
          {card.category==="Monstros"&&<p className="mt-3 text-sm font-semibold tabular-nums text-primary">
            ATK {card.atk??"—"} · DEF {card.def??"—"}
          </p>}
          {card.effect&&<p className="mt-3 line-clamp-4 text-xs text-muted">{card.effect}</p>}
        </div>
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
      <p className="mt-3 text-[11px] text-muted">Afaste o mouse ou pressione Esc para fechar.</p>
    </div>
  </>,document.body)
}
