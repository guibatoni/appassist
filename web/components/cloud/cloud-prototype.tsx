"use client"

import {useCallback,useEffect,useMemo,useState} from "react"
import {CloudOff,Gamepad2,Link2,LockKeyhole,RefreshCcw,ShieldCheck,Upload,CreditCard,Search} from "lucide-react"
import {
  cloudGet,cloudPost,cloudArt,type CloudCard,type CloudState,
  type CloudFusionResult,type CloudOpponentResult,type CloudDropResult,
  type CloudDeckResult,type CloudLiveResult,
} from "@/lib/cloud-local"

type Tab="cards"|"fusions"|"opponents"|"drops"|"decks"|"live"
const TABS:Array<[Tab,string]>=[
  ["cards","Cartas"],["fusions","Fusões"],["opponents","Oponentes"],
  ["drops","Drops"],["decks","Decks"],["live","Duelo ao vivo"],
]
const panel="rounded-xl border border-[#315174]/60 bg-[#09172b]/95 p-5"
const action="rounded-lg border border-[#3d7193] px-3 py-2 text-sm hover:bg-[#183a56] disabled:opacity-50"
function value(x:number|null|undefined){
  return typeof x==="number"?x.toLocaleString("pt-BR"):"—"
}
function ImageFromPC({token,sha,card}:{token:string;sha:string|null;card:CloudCard|null}){
  const [url,setUrl]=useState<string|null>(null)
  useEffect(()=>{
    let cancelled=false
    let objectUrl:string|null=null
    setUrl(null)
    if(sha&&card)void cloudArt(token,sha,card.id).then(result=>{
      if(cancelled){URL.revokeObjectURL(result);return}
      objectUrl=result;setUrl(result)
    }).catch(()=>setUrl(null))
    return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl)}
  },[token,sha,card])
  return <div className="flex min-h-48 items-center justify-center rounded-lg border border-[#2e5675] bg-[#020b16] p-2">
    {url?<img src={url} alt={card?.name||"Carta"} className="max-h-80 max-w-full object-contain"/>:
      <span className="text-center text-xs text-[#98a9c5]">Arte HD disponível somente quando extraída do mod local</span>}
  </div>
}

export function CloudPrototype(){
  const [pairKey,setPairKey]=useState("")
  const [token,setToken]=useState("")
  const [state,setState]=useState<CloudState|null>(null)
  const [tab,setTab]=useState<Tab>("cards")
  const [query,setQuery]=useState("")
  const [selectedCard,setSelectedCard]=useState<CloudCard|null>(null)
  const [opponent,setOpponent]=useState(0)
  const [deckId,setDeckId]=useState("")
  const [fusions,setFusions]=useState<CloudFusionResult|null>(null)
  const [opponents,setOpponents]=useState<CloudOpponentResult|null>(null)
  const [drops,setDrops]=useState<CloudDropResult|null>(null)
  const [decks,setDecks]=useState<CloudDeckResult|null>(null)
  const [live,setLive]=useState<CloudLiveResult|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState("")
  const [notice,setNotice]=useState("")

  const connect=async()=>{
    const key=pairKey.trim()
    setBusy(true);setError("")
    try{
      const result=await cloudGet<CloudState>(key,"/v1/state")
      if(result.storage!=="local-only"||result.cloudUpload!==false)throw Error("Connector incompatível")
      setState(result);setToken(key);setPairKey("")
      setNotice("Conexão local autenticada. Nenhum dado do jogo foi enviado à nuvem.")
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível conectar.")}
    finally{setBusy(false)}
  }
  const reloadState=useCallback(async()=>{
    if(token)setState(await cloudGet<CloudState>(token,"/v1/state"))
  },[token])

  const refresh=useCallback(async()=>{
    if(!token||!state?.activeSha)return
    try{
      if(tab==="fusions"){
        setFusions(await cloudGet<CloudFusionResult>(
          token,"/v1/fusions?limit=100&query="+encodeURIComponent(query)))
      }else if(tab==="opponents"){
        setOpponents(await cloudGet<CloudOpponentResult>(
          token,"/v1/opponents?opponent="+opponent))
      }else if(tab==="drops"){
        // Drop view also needs opponent names if opened first.
        setOpponents(await cloudGet<CloudOpponentResult>(
          token,"/v1/opponents?opponent="+opponent))
        setDrops(await cloudGet<CloudDropResult>(
          token,"/v1/drops?opponent="+opponent))
      }else if(tab==="decks"){
        setDecks(await cloudGet<CloudDeckResult>(
          token,"/v1/decks?deck="+encodeURIComponent(deckId)))
      }else if(tab==="live"){
        setLive(await cloudGet<CloudLiveResult>(token,"/v1/live"))
      }
      setError("")
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível ler os dados locais.")}
  },[token,state?.activeSha,tab,query,opponent,deckId])
  useEffect(()=>{
    if(!token||!state?.activeSha||tab==="cards")return
    void refresh()
    if(tab==="live"){
      const timer=window.setInterval(()=>void refresh(),1800)
      return()=>window.clearInterval(timer)
    }
  },[token,state?.activeSha,tab,refresh])

  const actionLocal=async(kind:"import"|"memory-card"|"activate",sha?:string)=>{
    setBusy(true);setError("");setNotice("")
    try{
      if(kind==="activate"){
        setState(await cloudPost<CloudState>(token,"/v1/activate",{sha}))
        setSelectedCard(null);setOpponent(0);setDeckId("")
        setFusions(null);setOpponents(null);setDrops(null);setDecks(null);setLive(null)
      }else{
        const response=await cloudPost<{cancelled?:boolean}>(
          token,kind==="import"?"/v1/import":"/v1/memory-card",
          {chooseLocalFile:true})
        await reloadState()
        if(response.cancelled){setNotice("Seleção cancelada.");return}
      }
      setNotice(kind==="import"?"ISO/BIN analisada localmente. Ative o mod.":
        kind==="memory-card"?"Memory Card selecionado localmente.":"Mod ativado.")
    }catch(e){setError(e instanceof Error?e.message:"Operação indisponível.")}
    finally{setBusy(false)}
  }
  const cards=useMemo(()=>state?.cards||[],[state])
  const visibleCards=useMemo(()=>{
    const q=query.trim().toLowerCase()
    return cards.filter(c=>!q||[c.id,c.name,c.type,c.description,c.effect]
      .filter(Boolean).join(" ").toLowerCase().includes(q)).slice(0,72)
  },[cards,query])

  return <div className="min-h-dvh bg-[#040a1a] px-4 py-7 text-[#e9f3ff] sm:px-7">
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2d5078] pb-5">
        <div className="flex items-center gap-3">
          <Gamepad2 className="size-9 text-[#68ccfa]"/>
          <div><h1 className="text-2xl font-extrabold tracking-wide text-[#f2be60]">DUELTRACE <span className="text-[#72c5ef]">CLOUD</span></h1>
            <p className="text-xs text-[#a4bdd8]">ALPHA · Extração e leitura no computador do jogador</p>
          </div>
        </div>
        <div className="rounded-full border border-[#326484] px-4 py-2 text-xs text-[#9bd7f4]">
          {token?"Connector local conectado":"Connector desconectado"}
        </div>
      </header>

      {!token?<div className="grid gap-5 lg:grid-cols-2">
        <section className={panel+" space-y-5"}>
          <div className="flex items-center gap-2"><Link2 className="size-6 text-[#69cdf8]"/>
            <h2 className="text-xl font-semibold">Conectar ao ePSXe e aos mods do PC</h2></div>
          <p className="text-sm text-[#adbed2]">O navegador comunica-se apenas com o DUELTRACE Connector no seu próprio Windows. As ISOs, Memory Cards e RAM nunca são enviados ao site.</p>
          <label className="block text-sm font-semibold" htmlFor="cloud-pair">Chave temporária do Connector</label>
          <input id="cloud-pair" value={pairKey} onChange={e=>setPairKey(e.target.value)}
            type="password" autoComplete="off" spellCheck={false} maxLength={128}
            placeholder="Cole aqui a chave que aparece no terminal"
            onKeyDown={e=>{if(e.key==="Enter")void connect()}}
            className="w-full rounded-lg border border-[#436686] bg-[#030d20] px-4 py-3 outline-none focus:border-[#68c9ff]"/>
          <button disabled={busy||pairKey.trim().length<24} onClick={()=>void connect()}
            className="flex items-center gap-2 rounded-lg bg-[#ebbd5a] px-5 py-3 font-bold text-[#12213a] hover:bg-[#ffd681] disabled:opacity-50">
            <LockKeyhole className="size-4"/>{busy?"Autenticando…":"Conectar ao computador"}
          </button>
          {error&&<p role="alert" className="text-sm text-[#ff9b9b]">{error}</p>}
        </section>
        <section className={panel+" space-y-4"}>
          <h2 className="text-lg font-semibold">Primeiro acesso</h2>
          <ol className="list-inside list-decimal space-y-2 text-sm text-[#b4c5db]">
            <li>Abra o projeto DUELTRACE no Windows.</li>
            <li>Execute o Connector local com Python.</li>
            <li>Copie a chave temporária exibida no terminal.</li>
            <li>Clique em Conectar e autorize o acesso local no navegador.</li>
          </ol>
          <code className="block overflow-x-auto rounded-lg bg-[#030d20] p-4 text-xs text-[#8cddff]">python scanner/dueltrace_cloud_connector.py</code>
          <p className="text-xs text-[#98b0ca]">Contas e assinatura ainda não fazem parte desta primeira prova funcional.</p>
        </section>
      </div>:
      <>
        <section className={panel+" space-y-3"}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-[#98b5d4]">ISO ativa</p>
              <h2 className="text-lg font-semibold text-[#f2c467]">{state?.activeName||"Nenhuma ISO ativada"}</h2>
              <p className="text-xs text-[#9cb1ce]">{cards.length} cartas carregadas somente do seu PC</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={()=>void reloadState()} className={action}><RefreshCcw className="inline size-4"/> Recarregar</button>
              <button disabled={busy} onClick={()=>void actionLocal("import")} className={action}><Upload className="inline size-4"/> Selecionar ISO/BIN</button>
              <button disabled={busy||!state?.activeSha} onClick={()=>void actionLocal("memory-card")} className={action}><CreditCard className="inline size-4"/> Memory Card</button>
              <button onClick={()=>{setToken("");setState(null);setSelectedCard(null);setLive(null)}} className={action}>Desconectar</button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {state?.mods.map(mod=><button key={mod.sha256} disabled={busy}
              onClick={()=>void actionLocal("activate",mod.sha256)}
              className={"rounded-full border px-3 py-1.5 text-xs disabled:opacity-50 "+
                (mod.sha256===state?.activeSha?"border-[#e6b34f] bg-[#57401c] text-[#fbe1a0]":
                  "border-[#35608b] bg-[#0b223f] hover:bg-[#183554]")}>{mod.name}</button>)}
          </div>
          {notice&&<p role="status" className="text-xs text-[#8be7b8]">{notice}</p>}
          {error&&<p role="alert" className="text-xs text-[#ff9a9a]">{error}</p>}
        </section>
        <nav aria-label="Seções do DUELTRACE Cloud" className="flex flex-wrap gap-2">
          {TABS.map(([id,label])=><button key={id} onClick={()=>{
            setTab(id);setQuery("");setError("");setSelectedCard(null)}}
            className={"rounded-lg border px-4 py-2.5 text-sm "+(tab===id?
              "border-[#e0af50] bg-[#ecbd5d] font-semibold text-[#102037]":
              "border-[#355477] bg-[#0c2039] hover:bg-[#1b3452]")}>{label}</button>)}
        </nav>
        {!state?.activeSha?<section className={panel}>
          Ative uma ISO/BIN já importada ou selecione um arquivo pelo botão acima.
        </section>:
        <section className="space-y-4">
          {(tab==="cards"||tab==="fusions")&&<label className="flex items-center gap-2 rounded-lg border border-[#315c81] bg-[#081930] px-4 py-3">
            <Search className="size-4 text-[#75d7ff]"/><input value={query} onChange={e=>setQuery(e.target.value)}
              placeholder="Nome, ID, tipo, efeito ou descrição"
              className="w-full bg-transparent text-sm outline-none"/>
          </label>}
          {tab==="cards"&&<div className="grid gap-4 lg:grid-cols-[1fr_285px]">
            <div className={panel}>
              <h3 className="mb-3 font-semibold">Biblioteca de cartas · {cards.length} cartas</h3>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {visibleCards.map(card=><button key={card.id} onClick={()=>setSelectedCard(card)}
                  className="rounded-lg border border-[#2c4b70] bg-[#08172c] p-3 text-left hover:border-[#77d1ff]">
                  <span className="text-xs text-[#79d4fd]">#{card.id}</span>
                  <h4 className="my-1 truncate text-sm font-semibold">{card.name}</h4>
                  <p className="truncate text-xs text-[#93afc9]">{card.type||card.category}</p>
                  <p className="mt-1 text-xs text-[#eebd67]">ATK {value(card.atk)} · DEF {value(card.def)}</p>
                </button>)}
              </div>
            </div>
            <aside className={panel+" space-y-3"}>
              {selectedCard?<><ImageFromPC token={token} sha={state.activeSha} card={selectedCard}/>
                <h3 className="font-bold text-[#f2bd67]">{selectedCard.name}</h3>
                <p className="text-xs text-[#adc0d2]">#{selectedCard.id} · {selectedCard.type} · ATK {value(selectedCard.atk)} / DEF {value(selectedCard.def)}</p>
                {selectedCard.description&&<p className="whitespace-pre-wrap text-sm text-[#cbd5e5]">{selectedCard.description}</p>}
                {selectedCard.effect&&<p className="whitespace-pre-wrap text-sm text-[#7fcdec]">{selectedCard.effect}</p>}
              </>:<p className="text-sm text-[#a6bbd4]">Clique em uma carta para exibir a arte HD e as informações extraídas da ISO.</p>}
            </aside>
          </div>}
          {tab==="fusions"&&<div className={panel}>
            <h3 className="mb-3 font-semibold">Fusões disponíveis · {fusions?.total??0} combinações</h3>
            <div className="grid gap-2 md:grid-cols-2">
              {fusions?.rows.map((row,i)=><div key={row.a+"-"+row.b+"-"+i} className="rounded-lg border border-[#2c4b70] p-3 text-sm">
                <span>{row.nameA} + {row.nameB} </span><strong className="text-[#efc574]">= {row.nameResult}</strong>
                <p className="mt-1 text-xs text-[#9baec9]">{row.source}</p>
              </div>)}
            </div>
          </div>}
          {(tab==="opponents"||tab==="drops")&&<div className={panel+" space-y-3"}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">{tab==="opponents"?"Deck dos oponentes":"Drops do adversário"}</h3>
              <select value={opponent} onChange={e=>setOpponent(Number(e.target.value))}
                className="rounded-lg border border-[#355878] bg-[#081930] px-3 py-2 text-sm">
                <option value={0}>Primeiro oponente</option>
                {opponents?.opponents.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
            <p className="text-xs text-[#abc0d8]">{tab==="opponents"?opponents?.status:drops?.status}</p>
            {(tab==="opponents"?opponents?.provisional:drops?.provisional)&&
              <p className="text-xs text-[#eec274]">Dados candidatos, ainda não confirmados em duelo.</p>}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {tab==="opponents"?opponents?.cards.map(c=><div key={c.id} className="rounded-lg border border-[#29496d] p-3">
                <p className="text-xs text-[#7cccf5]">#{c.id}</p><p className="font-semibold">{c.name}</p>
                <p className="text-xs text-[#adc1d8]">Peso {c.weight}</p>
              </div>):
              drops?.rows.map((c,i)=><div key={c.cardId+"-"+i} className="rounded-lg border border-[#29496d] p-3">
                <p className="text-xs text-[#7cccf5]">#{c.cardId} · {c.groupLabel}</p>
                <p className="font-semibold">{c.cardName}</p>
                <p className="text-xs text-[#adc1d8]">{value(c.chancePercent)}%</p>
              </div>)}
            </div>
          </div>}
          {tab==="decks"&&<div className={panel+" space-y-4"}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">Deck e fusões do jogador</h3>
              <select value={deckId} onChange={e=>setDeckId(e.target.value)}
                className="max-w-full rounded-lg border border-[#355878] bg-[#081930] px-3 py-2 text-sm">
                <option value="">Deck ativo ou gravado</option>
                {decks?.saved.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <p className="text-xs text-[#adc1d8]">{decks?.status}</p>
            <p className="text-xs text-[#efc574]">{decks?.saveDisplayName}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {decks?.cards.map(c=><div key={c.id} className="rounded-lg border border-[#29496d] p-3 text-sm">
                <p className="text-xs text-[#7cccf5]">#{c.id} · {c.count}x</p><p className="font-semibold">{c.name}</p>
              </div>)}
            </div>
            <h4 className="font-semibold text-[#eabf69]">Fusões possíveis: {decks?.fusions.total??0}</h4>
            <div className="grid gap-2 md:grid-cols-2">
              {decks?.fusions.rows.slice(0,30).map((f,i)=><div key={i} className="rounded-lg border border-[#29496d] p-3 text-sm">
                {f.nameA} + {f.nameB} <strong className="text-[#eabf69]">= {f.nameResult}</strong>
              </div>)}
            </div>
          </div>}
          {tab==="live"&&<div className="grid gap-4 lg:grid-cols-2">
            <div className={panel+" space-y-3"}>
              <h3 className="font-semibold">Mão ao vivo · ePSXe</h3>
              <p className="text-xs text-[#a3bdda]">{live?.hand.status||"Aguardando o emulador…"}</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {live?.hand.cards.map((c,i)=><div key={c.id+"-"+i} className="rounded-lg border border-[#29496d] p-3 text-sm">
                  <p className="text-xs text-[#7cccf5]">Posição {c.slot}</p><p className="font-semibold">{c.name}</p>
                  <p className="text-xs">ATK {value(c.atk)}</p>
                </div>)}
              </div>
              {(live?.hand.pairs?.length||0)>0&&<div className="space-y-2 border-t border-[#29496d] pt-3">
                <h4 className="font-semibold text-[#edc16e]">Até 5 fusões possíveis da mão</h4>
                {live!.hand.pairs.slice(0,5).map((p,i)=><div key={i}
                  className="rounded-lg border border-[#29496d] p-2 text-xs">
                  Posições {p.slot_a} + {p.slot_b}: <strong className="text-[#92dcff]">{p.result_name}</strong>
                  <span className="ml-2 text-[#aec5d8]">ATK {value(p.atk)}</span>
                </div>)}
              </div>}
              {(live?.hand.chains?.length||0)>0&&<div className="space-y-1">
                <h4 className="font-semibold text-[#edc16e]">Rotas de fusão</h4>
                {live!.hand.chains.slice(0,5).map((route,i)=><div key={i}
                  className="text-xs text-[#abc9df]">
                  {route.result_name} · ATK {value(route.atk)}
                </div>)}
              </div>}
            </div>
            <div className={panel+" space-y-3"}>
              <h3 className="font-semibold">RANK ao vivo</h3>
              <div className="text-4xl font-bold text-[#eec579]">{live?.rank.category||"—"}</div>
              <p className="text-sm text-[#a3bdda]">Pontuação: {value(live?.rank.score)}</p>
              <p className="text-xs text-[#a3bdda]">{live?.rank.status||"Aguardando leitura local…"}</p>
            </div>
          </div>}
        </section>}
      </>}
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[#29496e] pt-5 text-xs text-[#9bb2cd]">
        <span className="flex items-center gap-2"><CloudOff className="size-4"/> ISO, Memory Card e RAM permanecem no PC</span>
        <span className="flex items-center gap-2"><ShieldCheck className="size-4"/> Conexão local autenticada</span>
        <span>Batoni Dev · DUELTRACE Cloud Alpha</span>
      </footer>
    </div>
  </div>
}
