"use client"

/**
 * DUELTRACE RANK typography — shared by the duel panel and the floating visor.
 * Only visual formatting is changed: score/rank computation remains in Python.
 * The Z rank belongs to Remaster X15 and is intentionally kept gold, since
 * the requested S/A/B/C/D palette does not define a Z color.
 */
type RankBand = "S"|"A"|"B"|"C"|"D"|"Z"
type PowerMode = "POW"|"TEC"

const BAND_COLORS:Record<RankBand,string>={
  S:"text-[#ff4dd7]",
  A:"text-[#ff5353]",
  B:"text-[#facc15]",
  C:"text-[#4ade80]",
  D:"text-[#9ca3af]",
  Z:"text-gold",
}

const MODE_COLORS:Record<PowerMode,string>={
  POW:"border border-[#ef555d]/75 bg-[#b42332] text-white",
  TEC:"border border-[#579bf8]/75 bg-[#1554ab] text-white",
}

export function splitRankCategory(category:string|null|undefined):{
  grade:RankBand;mode:PowerMode
}|null{
  if(!category)return null
  const match=/^\s*([SABCDZ])\s*[-– ]\s*(POW|TEC)\s*$/i.exec(category)
  if(!match)return null
  return {grade:match[1].toUpperCase() as RankBand,
          mode:match[2].toUpperCase() as PowerMode}
}

export function RankCategory({category,large=false}:{
  category:string|null|undefined;large?:boolean
}){
  const split=splitRankCategory(category)
  if(!split)return <span className="font-display text-base font-semibold text-muted">
    {category||"—"}
  </span>
  return <span className="inline-flex max-w-full items-center justify-center gap-2"
    aria-label={`Nota ${split.grade}, ${split.mode}`}>
    <span className={`font-display font-extrabold drop-shadow-sm ${BAND_COLORS[split.grade]} `+
      (large?"text-5xl":"text-3xl")}>
      {split.grade}
    </span>
    <span className={`inline-flex min-h-8 items-center rounded-md px-3 py-1 text-sm font-extrabold tracking-wider shadow-sm ${MODE_COLORS[split.mode]}`+
      (large?" sm:text-base":"")}>
      {split.mode}
    </span>
  </span>
}

export function RankScoreDisplay({score,category,large=false}:{
  score:number|null|undefined;category:string|null|undefined;large?:boolean
}){
  const ready=typeof score==="number"&&Number.isFinite(score)
  return <div className="flex flex-col items-center justify-center gap-3 text-center"
    aria-label="Placar e classificação de RANK">
    <div className="font-display tabular-nums">
      <span className={`font-bold text-white ${large?"text-6xl":"text-4xl"}`}>
        {ready?score:"—"}
      </span>
      <span className="ml-2 text-sm font-medium text-muted">pts</span>
    </div>
    <RankCategory category={category} large={large}/>
  </div>
}
