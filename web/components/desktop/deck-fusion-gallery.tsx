"use client"

import {useMemo,useState} from "react"
import type {DeckLibrary} from "@/lib/desktop"
import {CardFace} from "./deck-card-face"

const normalize=(value:string)=>value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("pt-BR").trim()

/** Display ALL source-bound fusion pairs (not just the first 80).
 * Client filters never change recipes, ranks or cards in the mod profile.
 */
export function DeckFusionGallery({state,sha,onCardClick}:{
  state:DeckLibrary|null;sha:string|null;onCardClick:(id:number)=>void
}) {
  const [query,setQuery]=useState("")
  const [amount,setAmount]=useState("10")
  const rows=state?.fusions?.rows??[]
  const matching=useMemo(()=>{
    const q=normalize(query)
    if(!q)return rows
    return rows.filter(row=>normalize([
      row.nameA,row.nameB,row.nameResult,
      "#"+row.a,"#"+row.b,"#"+row.result,
    ].join(" ")).includes(q))
  },[rows,query])
  const shown=amount==="all"?matching:matching.slice(0,Number(amount))
  return <section className="panel rounded-xl p-4" aria-label="Fusões possíveis com este deck">
    <h2 className="font-display text-lg font-semibold text-gold">Fusões possíveis com este deck</h2>
    <p className="mt-1 text-xs text-muted">
      Materiais e resultado com miniaturas. As receitas dependem dos dados extraídos da ISO ativa.
    </p>
    {state?.fusions?.provisional&&<p className="mt-2 text-xs text-gold">
      Inclui receitas candidatas ainda não confirmadas durante uma partida.
    </p>}
    <div className="mt-3 flex flex-wrap items-end gap-3">
      <label className="flex min-w-44 flex-1 flex-col gap-1 text-xs text-muted">
        Pesquisar carta da fusão
        <input className="field px-3 py-2 text-sm" value={query}
          onChange={e=>setQuery(e.target.value)}
          placeholder="Nome ou ID de material / resultado"
          aria-label="Pesquisar fusões por nome de carta"/>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Quantidade a mostrar
        <select className="field px-3 py-2 text-sm" value={amount}
          onChange={e=>setAmount(e.target.value)}
          aria-label="Quantidade de fusões exibidas">
          {[1,5,10,20,50,100,200].map(n=><option key={n} value={String(n)}>{n} fusões</option>)}
          <option value="all">Todas as fusões</option>
        </select>
      </label>
    </div>
    <p className="mt-3 text-sm text-primary" aria-live="polite">
      Mostrando {shown.length} de {matching.length} fusões encontradas
      {query?" na pesquisa":""} · {state?.fusions?.total??0} no deck
    </p>
    {matching.length===0&&<p className="mt-3 text-sm text-muted">
      Nenhuma fusão encontrada com esse nome. Altere a pesquisa ou selecione outro deck.
    </p>}
    <div className="mt-3 grid gap-3 xl:grid-cols-2">
      {shown.map((row,index)=><article key={row.a+"-"+row.b+"-"+row.result+"-"+index}
        className="rounded-xl border border-line/60 bg-[#09172d] p-3">
        <div className="flex flex-wrap items-start justify-center gap-2 sm:flex-nowrap">
          {([
            {id:row.a,name:row.nameA,label:"Material 1"},
            {id:row.b,name:row.nameB,label:"Material 2"},
            {id:row.result,name:row.nameResult,label:"Resultado"},
          ] as const).map((card,pos)=><div className="contents" key={pos}>
            {pos===1&&<span className="self-center font-display text-lg text-primary" aria-hidden="true">+</span>}
            {pos===2&&<span className="self-center font-display text-lg text-gold" aria-hidden="true">=</span>}
            <button type="button" onClick={()=>onCardClick(card.id)}
              className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-lg p-1 text-center hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              title={"Ver "+card.name} aria-label={"Ver "+card.label+": "+card.name}>
              <CardFace sha={sha} id={card.id} name={card.name} width="w-14 sm:w-16"/>
              <span className="w-full truncate text-[10px] text-muted">{card.label}</span>
              <span className="w-full truncate text-xs font-medium text-white">{card.name}</span>
              <span className="text-[10px] text-primary">#{card.id}</span>
            </button>
          </div>)}
        </div>
        <p className="mt-2 text-[11px] text-muted">Fonte: {row.source}</p>
      </article>)}
    </div>
  </section>
}
