"use client"

import {useEffect,useState} from "react"
import Image from "next/image"
import {Calculator,Swords,X} from "lucide-react"
import {desktopApi,useDesktopState,cardClassicHd,cardArtHd,cardWithFrame,cardArt} from "@/lib/desktop"
import type {HandState,RankState,LocalCard} from "@/lib/desktop"
import {RankScoreDisplay} from "./rank-score-display"

/**
 * Windows can stay visible above ePSXe or while the main application is
 * minimized. Pop-ups are passive viewers: no SPOILS forms, no controls for
 * selecting recipes, and no button that changes duel state.
 */
function VisorHeader({name,kind}:{
  name:string;kind:"calculadora"|"fusoes"
}){
  const [error,setError]=useState(false)
  return <header className="mb-3 flex items-center justify-between gap-2">
    <div>
      <h1 className="font-display text-base font-bold text-gold">{name}</h1>
      <p className="text-[11px] text-muted">Visor automático · DUELTRACE</p>
    </div>
    <button type="button" className="btn-ghost shrink-0 px-2 py-2"
      aria-label="Fechar visor" title="Fechar visor"
      onClick={async()=>{
        try{await desktopApi()?.close_tool_window(kind)}
        catch{setError(true)}
      }}>
      <X className="size-4"/>
    </button>
    {error&&<p role="alert" className="text-xs text-danger">
      Feche pelo X da janela.
    </p>}
  </header>
}

export function FloatingCalculator(){
  const {state}=useDesktopState()
  const [live,setLive]=useState<RankState|null>(null)

  useEffect(()=>{
    let mounted=true
    let reading=false
    setLive(null)
    const update=async()=>{
      const api=desktopApi()
      if(!api||reading)return
      reading=true
      try{
        const value=await api.get_rank_auto()
        if(mounted)setLive(value)
      }catch{
        if(mounted)setLive(null)
      }finally{reading=false}
    }
    void update()
    const poll=window.setInterval(()=>void update(),850)
    return()=>{mounted=false;window.clearInterval(poll)}
  },[state?.activeSha])

  const ready=live?.ready===true
  return <div className="mx-auto max-w-md">
    <VisorHeader name="Calculadora · RANK ao vivo" kind="calculadora"/>
    <section className="panel rounded-xl px-3 py-4" aria-label="Visor de RANK automático">
      <div className="mb-4 flex items-center justify-center gap-2 text-xs text-muted">
        <Calculator className="size-4 text-primary"/>
        <span className="max-w-[260px] truncate" title={state?.activeName??""}>
          {state?.activeName??"Nenhuma ISO ativa"}
        </span>
      </div>
      <RankScoreDisplay score={ready?live.score:null}
        category={ready?live.category:null} large/>
      <p role="status" className="mt-4 text-center text-[11px] text-muted">
        {ready?"Pontuação estimada · atualização automática":"Aguardando duelo."}
      </p>
    </section>
  </div>
}

function FusionTipCard({card,sha,label,fallback}:{
  card:LocalCard|null|undefined;sha:string|null;label:string;fallback?:string
}){
  const [mode,setMode]=useState<"classic"|"hd"|"frame"|"art"|"none">("classic")
  useEffect(()=>setMode("classic"),[sha,card?.id])
  const img=card&&sha?(mode==="classic"?cardClassicHd(sha,card.id):
    mode==="hd"?cardArtHd(sha,card.id):
    mode==="frame"?cardWithFrame(sha,card.id):
    mode==="art"?cardArt(sha,card.id):null):null
  return <div className="flex min-w-[3.5rem] max-w-24 flex-[1_1_3.5rem] flex-col items-center gap-1">
    <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
    <div className="relative aspect-[9/13] w-[64px] shrink-0 overflow-hidden rounded border border-gold/30 bg-background/75 min-[390px]:w-[78px]">
      {img?<Image src={img} alt={card?.name??"Carta"} fill unoptimized sizes="78px"
        className="object-contain"
        onError={()=>setMode(old=>old==="classic"?"hd":old==="hd"?"frame":old==="frame"?"art":"none")}/>:
        <div className="flex h-full items-center justify-center text-xs text-primary">
          {card?`#${card.id}`:"—"}
        </div>}
    </div>
    <p className="line-clamp-2 min-h-8 break-words text-center text-[11px] font-semibold text-white">
      {card?.name??fallback??"Carta"}
    </p>
    {card&&<p className="text-[10px] text-gold">#{card.id}</p>}
  </div>
}

export function FloatingFusionTips(){
  const {state}=useDesktopState()
  const [hand,setHand]=useState<HandState|null>(null)
  const [error,setError]=useState(false)
  const cardsById=new Map((state?.cards??[]).map(card=>[card.id,card]))

  useEffect(()=>{
    let mounted=true
    let reading=false
    setHand(null)
    setError(false)
    const update=async()=>{
      const api=desktopApi()
      if(!api||reading)return
      reading=true
      try{
        const value=await api.get_hand()
        if(mounted){setHand(value);setError(false)}
      }catch{
        if(mounted){setHand(null);setError(true)}
      }finally{reading=false}
    }
    void update()
    const poll=window.setInterval(()=>void update(),1300)
    return()=>{mounted=false;window.clearInterval(poll)}
  },[state?.activeSha])

  const pairs=hand?.ready?hand.pairs:[]
  const chains=hand?.ready?hand.chains:[]
  const hasAny=pairs.length>0||chains.length>0
  return <div className="mx-auto max-w-lg">
    <VisorHeader name="Dicas de fusões" kind="fusoes"/>
    <p className="mb-3 truncate text-xs text-muted">
      <Swords className="mr-1 inline size-4 text-primary"/>
      {state?.activeName??"Nenhuma ISO ativa"}
    </p>
    <div className="panel space-y-3 rounded-xl p-3">
      <p role="status" className="text-xs text-muted">
        {error?"Leitura temporariamente indisponível.":
          hand?.status??"Aguardando mão do ePSXe."}
      </p>
      {hand?.ready&&!hasAny&&<p className="py-4 text-center text-sm text-muted">
        Nenhuma fusão encontrada para as cartas atuais.
      </p>}
      {pairs.length>0&&<section aria-label="Fusões em dupla">
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-primary">
          Duplas · {pairs.length}
        </h2>
        <div className="space-y-2">
          {pairs.slice(0,3).map((item,i)=>
            <div key={`${item.slot_a}-${item.slot_b}-${item.result}-${i}`}
              className="rounded-md border border-line/70 bg-background/40 px-3 py-2">
              <p className="mb-2 text-center text-[11px] text-muted">
                Mão {item.slot_a} + {item.slot_b}
              </p>
              <div className="flex flex-wrap items-center justify-center gap-1">
                <FusionTipCard label="Material" sha={state?.activeSha??null}
                  card={hand?.hand[item.slot_a-1]??cardsById.get(item.a)}/>
                <span className="text-primary">+</span>
                <FusionTipCard label="Material" sha={state?.activeSha??null}
                  card={hand?.hand[item.slot_b-1]??cardsById.get(item.b)}/>
                <span className="text-gold">→</span>
                <FusionTipCard label="Resultado" sha={state?.activeSha??null}
                  card={cardsById.get(item.result)} fallback={item.result_name}/>
              </div>
            </div>)}
        </div>
        {pairs.length>3&&<p className="mt-2 text-[11px] text-muted">
          +{pairs.length-3} combinações adicionais na aba Fusões.
        </p>}
      </section>}
      {chains.length>0&&<section aria-label="Fusões em cadeia">
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-primary">
          Cadeias · {chains.length}
        </h2>
        <div className="space-y-2">
          {chains.slice(0,Math.max(0,5-Math.min(3,pairs.length))).map((item,i)=>
            <div key={`${item.result}-${item.slot_order.join("-")}-${i}`}
              className="rounded-md border border-line/70 bg-background/40 px-3 py-2">
              <p className="mb-2 text-[11px] text-muted">
                Ordem da mão: {item.slot_order.join(" → ")}
              </p>
              <div className="flex flex-wrap items-start justify-center gap-1">
                {item.slot_order.map((slot,i)=><FusionTipCard key={i} label={`Pos. ${slot}`}
                  sha={state?.activeSha??null}
                  card={hand?.hand[slot-1]??null}/>)}
                <span className="self-center text-gold">→</span>
                <FusionTipCard label="Resultado" sha={state?.activeSha??null}
                  card={cardsById.get(item.result)} fallback={item.result_name}/>
              </div>
            </div>)}
        </div>
        {chains.length>Math.max(0,5-Math.min(3,pairs.length))&&<p className="mt-2 text-[11px] text-muted">
          +{chains.length-Math.max(0,5-Math.min(3,pairs.length))} cadeias adicionais na aba Fusões.
        </p>}
        {hand?.chainsComplete===false&&<p className="mt-2 text-[11px] text-gold">
          Busca de cadeias parcial.
        </p>}
      </section>}
    </div>
    <p className="mt-2 text-[11px] text-muted">
      Sugestões estruturais podem exigir confirmação em duelo.
    </p>
  </div>
}
