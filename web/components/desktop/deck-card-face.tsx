"use client"

import Image from "next/image"
import {useEffect,useState} from "react"
import {Layers} from "lucide-react"
import {cardClassicHd,cardArtHd,cardArt,cardWithFrame} from "@/lib/desktop"

export function CardFace({sha,id,name,width="w-24"}:{
  sha:string|null;id:number;name:string;width?:string
}) {
  const [source,setSource]=useState<"classic"|"hd"|"frame"|"art"|"none">("classic")
  useEffect(()=>setSource("classic"),[sha,id])
  const url=source==="classic"?cardClassicHd(sha,id):
    source==="hd"?cardArtHd(sha,id):source==="frame"?cardWithFrame(sha,id):
    source==="art"?cardArt(sha,id):null
  return <div className={"relative aspect-[9/13] shrink-0 overflow-hidden rounded-lg border border-gold/45 bg-[#071428] "+width}>
    {url?<Image src={url} alt={"Carta "+name} fill unoptimized sizes="144px"
      className={source==="frame"?"object-fill":"object-contain"}
      onError={()=>setSource(old=>old==="classic"?"hd":old==="hd"?"frame":old==="frame"?"art":"none")}/>:
    <div className="flex h-full items-center justify-center"><Layers className="size-7 text-primary/50"/></div>}
  </div>
}
