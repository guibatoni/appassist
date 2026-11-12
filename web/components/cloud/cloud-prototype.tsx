"use client"

import {useCallback,useEffect,useMemo,useState} from "react"
import {CloudOff,Gamepad2,Link2,LockKeyhole,RefreshCcw,ShieldCheck,Upload,CreditCard,Search,Settings2,BookOpen,Layers,Users,Gift} from "lucide-react"
import {useCloudUi} from "@/lib/cloud-ui"
import {
  cloudGet,cloudPost,cloudArt,type CloudCard,type CloudState,
  type CloudFusionResult,type CloudOpponentResult,type CloudDropResult,
  type CloudDeckResult,type CloudLiveResult,
} from "@/lib/cloud-local"

const panel="panel rounded-xl border-line/60 p-4"
const action="btn-ghost text-sm disabled:opacity-50"
const head="panel rounded-xl border-gold/40 bg-gradient-to-r from-[#142b51] to-[#061126] px-4 py-4"

function value(x:number|null|undefined){
  return typeof x==="number"?x.toLocaleString("pt-BR"):"—"
}
function ImageFromPC({token,sha,card,compact=false}:{token:string;sha:string|null;card:CloudCard|null;compact?:boolean}){
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
  return <div className={"relative flex items-center justify-center overflow-hidden rounded-md border border-gold/40 bg-[#061126] "+(compact?"mx-auto aspect-[65/90] w-full max-w-28":"min-h-48 p-2")}>
    {url?<img src={url} alt={card?.name||"Carta"} className="h-full w-full object-contain"/>:
      compact?<Layers className="size-7 text-primary/45" aria-label="Arte local indisponível"/>:
      <span className="text-center text-xs text-muted">Arte HD disponível somente quando extraída do mod local</span>}
  </div>
}

export function CloudPrototype(){
  const [pairKey,setPairKey]=useState("")
  const [token,setToken]=useState("")
  const [state,setState]=useState<CloudState|null>(null)
  const {tab,setTab,setConnected}=useCloudUi()
  const [query,setQuery]=useState("")
  const [selectedCard,setSelectedCard]=useState<CloudCard|null>(null)
  const [page,setPage]=useState(0)
  const [pageSize,setPageSize]=useState(20)
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
    setError("")
    if(key.length<24){
      setError("A chave está incompleta. Copie a chave temporária inteira do PowerShell (mínimo de 24 caracteres).")
      return
    }
    setBusy(true)
    try{
      const result=await cloudGet<CloudState>(key,"/v1/state")
      if(result.storage!=="local-only"||result.cloudUpload!==false)throw Error("Connector incompatível")
      setState(result);setToken(key);setPairKey("")
      setConnected(true);setTab("mods")
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
      if(tab==="fusoes"){
        setFusions(await cloudGet<CloudFusionResult>(
          token,"/v1/fusions?limit=100&query="+encodeURIComponent(query)))
      }else if(tab==="oponentes"){
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
      }else if(tab==="inicio"){
        setLive(await cloudGet<CloudLiveResult>(token,"/v1/live"))
      }
      setError("")
    }catch(e){setError(e instanceof Error?e.message:"Não foi possível ler os dados locais.")}
  },[token,state?.activeSha,tab,query,opponent,deckId])
  useEffect(()=>{
    if(!token||!state?.activeSha||tab==="biblioteca")return
    void refresh()
    if(tab==="inicio"){
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
      if(kind==="activate")setTab("biblioteca")
    }catch(e){setError(e instanceof Error?e.message:"Operação indisponível.")}
    finally{setBusy(false)}
  }
  const cards=useMemo(()=>state?.cards||[],[state])
  const cardsById=useMemo(()=>new Map(cards.map(c=>[c.id,c])),[cards])
  const visibleCards=useMemo(()=>{
    const q=query.trim().toLowerCase()
    return cards.filter(c=>!q||[c.id,c.name,c.type,c.description,c.effect]
      .filter(Boolean).join(" ").toLowerCase().includes(q))
  },[cards,query])

  return <div className="flex min-w-0 flex-col gap-4 py-2">
    <div className={head}>
      <div className="flex items-center gap-3">
        <Gamepad2 className="size-7 text-gold"/>
        <div><h1 className="font-display text-2xl font-bold text-gold">DUELTRACE Cloud</h1>
          <p className="text-sm text-muted">MultiMod Companion · Alpha local-first</p>
        </div>
      </div>
    </div>
      {!token?<div className="grid gap-5 lg:grid-cols-2">
        <section className={panel+" space-y-5"}>
          <div className="flex items-center gap-2"><Link2 className="size-6 text-primary"/>
            <h2 className="font-display text-xl font-semibold text-gold">Conectar ao ePSXe e aos mods do PC</h2></div>
          <p className="text-sm text-[#adbed2]">O navegador comunica-se apenas com o DUELTRACE Connector no seu próprio Windows. As ISOs, Memory Cards e RAM nunca são enviados ao site.</p>
          <label className="block text-sm font-semibold" htmlFor="cloud-pair">Chave temporária do Connector</label>
          <input id="cloud-pair" value={pairKey} onChange={e=>{setPairKey(e.target.value);setError("")}}
            type="password" autoComplete="off" spellCheck={false} maxLength={128}
            placeholder="Cole aqui a chave que aparece no terminal"
            onKeyDown={e=>{if(e.key==="Enter"&&!busy)void connect()}}
            className="field w-full px-4 py-3 text-white outline-none focus:border-primary"/>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>Chave recebida: {pairKey.trim().length} caracteres</span>
            {pairKey.trim().length>=24&&<span className="text-success">Pronta para autenticar</span>}
          </div>
          <button type="button" disabled={busy} onClick={()=>void connect()}
            className="btn-gold min-h-11 px-5 py-3 font-semibold disabled:opacity-50">
            <LockKeyhole className="size-4"/>{busy?"Conectando…":"Conectar ao computador"}
          </button>
          {busy&&<p role="status" className="text-sm text-primary">Consultando o Connector local em 127.0.0.1:8765…</p>}
          {error&&<p role="alert" className="text-sm text-danger">{error}</p>}
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
              <button onClick={()=>{setToken("");setState(null);setSelectedCard(null);setLive(null);setConnected(false);setTab("inicio")}} className={action}>Desconectar</button>
            </div>
          </div>
          {tab==="mods"&&<div className="flex flex-wrap gap-2">
            {state?.mods.map(mod=><button key={mod.sha256} disabled={busy}
              onClick={()=>void actionLocal("activate",mod.sha256)}
              className={"rounded-lg border px-3 py-2 text-xs disabled:opacity-50 "+
                (mod.sha256===state?.activeSha?"border-gold bg-gold/15 text-gold":
                  "border-line text-foreground hover:border-primary hover:bg-primary/10")}>{mod.name}</button>)}
          </div>}
          {notice&&<p role="status" className="text-xs text-[#8be7b8]">{notice}</p>}
          {error&&<p role="alert" className="text-xs text-[#ff9a9a]">{error}</p>}
        </section>
        {tab==="configuracoes"?<section className={panel+" space-y-4"}>
          <h2 className="font-display text-xl font-bold text-gold">Configurações</h2>
          <p className="text-sm text-muted">A interface web utiliza os mesmos elementos visuais do DUELTRACE Windows. Os dados de jogo são processados exclusivamente no computador.</p>
          <p className="font-semibold text-white">Desenvolvido por Batoni Dev - Guilherme Batoni</p>
          <p className="rounded-lg border border-gold/40 p-3 text-sm text-gold">Não permitida a distribuição do aplicativo.</p>
        </section>:tab==="mods"?<section className={panel+" space-y-3"}>
          <h2 className="font-display text-xl font-bold text-gold">Biblioteca de Mods</h2>
          <p className="text-sm text-muted">Importe arquivos ISO/BIN com o seletor Windows do Connector e ative o mod desejado.</p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {state?.mods.map(mod=><button key={mod.sha256} type="button" disabled={busy}
              onClick={()=>void actionLocal("activate",mod.sha256)}
              className={"rounded-xl border bg-panel-strong/70 p-4 text-left hover:border-primary "+
                (state?.activeSha===mod.sha256?"border-gold":"border-line")}>
              <p className="font-semibold text-white">{mod.name}</p>
              <p className="mt-2 text-xs text-muted">{mod.cards} cartas · {mod.fusions} fusões · {mod.opponents} oponentes</p>
              <p className="mt-2 text-xs text-primary">{state?.activeSha===mod.sha256?"Mod ativo":"Ativar mod"}</p>
            </button>)}
          </div>
        </section>:!state?.activeSha?<section className={panel}>
          Ative uma ISO/BIN já importada em Biblioteca de Mods ou selecione um arquivo pelo botão acima.
        </section>:
        <section className="space-y-4">
          {(tab==="biblioteca"||tab==="fusoes")&&<label className="flex items-center gap-2 rounded-lg border border-[#315c81] bg-[#081930] px-4 py-3">
            <Search className="size-4 text-[#75d7ff]"/><input value={query} onChange={e=>setQuery(e.target.value)}
              placeholder="Nome, ID, tipo, efeito ou descrição"
              className="w-full bg-transparent text-sm outline-none"/>
          </label>}
          {tab==="biblioteca"&&<section className={panel}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-display text-xl font-bold text-gold">Biblioteca de Cartas</h2>
              <label className="flex items-center gap-2 text-xs text-muted">Cartas por página
                <select className="field px-2 py-2" value={pageSize}
                  onChange={e=>{setPageSize(Number(e.target.value));setPage(0)}}>
                  {[10,20,30,40,50].map(n=><option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
              {visibleCards.slice(page*pageSize,(page+1)*pageSize).map(card=><button key={card.id}
                onClick={()=>setSelectedCard(card)}
                className="rounded-lg border border-line/70 bg-panel-strong/60 p-2 text-center hover:border-primary hover:bg-primary/10">
                <ImageFromPC token={token} sha={state.activeSha} card={card} compact/>
                <p className="mt-2 min-h-8 break-words text-xs font-semibold text-white">{card.name}</p>
                <p className="mt-1 text-[11px] text-primary">ATK {value(card.atk)} · DEF {value(card.def)}</p>
              </button>)}
            </div>
            {!visibleCards.length&&<p className="mt-4 text-sm text-muted">Nenhuma carta encontrada.</p>}
            <div className="mt-4 flex items-center justify-center gap-3">
              <button className="btn-ghost disabled:opacity-30" disabled={page===0} onClick={()=>setPage(n=>n-1)}>Anterior</button>
              <span className="text-xs text-muted">{page+1} / {Math.max(1,Math.ceil(visibleCards.length/pageSize))}</span>
              <button className="btn-ghost disabled:opacity-30"
                disabled={(page+1)*pageSize>=visibleCards.length} onClick={()=>setPage(n=>n+1)}>Próxima</button>
            </div>
          </section>}
          {tab==="fusoes"&&<section className={panel+" space-y-4"}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-display text-xl font-bold text-gold">Biblioteca de Fusões</h2>
              <p className="text-sm text-primary">{fusions?.total??0} combinações extraídas da ISO ativa</p>
            </div>
            {fusions?.provisional&&<p className="text-xs text-gold">Existem receitas candidatas ainda não confirmadas em duelo.</p>}
            <div className="dt-adaptive-cards">
              {fusions?.rows.map((row,i)=><article key={row.a+"-"+row.b+"-"+row.result+"-"+i}
                className="rounded-xl border border-line/80 bg-gradient-to-br from-panel-strong/90 via-[#0b1a35] to-background p-3">
                <div className="grid grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)] items-center gap-1">
                  {([
                    {id:row.a,name:row.nameA,role:"Material A"},
                    {id:row.b,name:row.nameB,role:"Material B"},
                    {id:row.result,name:row.nameResult,role:"Resultado"},
                  ] as const).map((c,index)=><div key={c.id+"-"+index} className="contents">
                    {index>0&&<span className={"text-center font-display text-xl "+(index===1?"text-primary":"text-gold")}>
                      {index===1?"+":"→"}
                    </span>}
                    <button className="flex min-w-0 flex-col items-center gap-1 text-center"
                      type="button" onClick={()=>setSelectedCard(cardsById.get(c.id)??null)}>
                      <p className="text-[10px] uppercase text-muted">{c.role}</p>
                      <ImageFromPC token={token} sha={state.activeSha} card={cardsById.get(c.id)??null} compact/>
                      <span className="text-xs font-semibold text-gold">#{c.id}</span>
                      <span className="line-clamp-2 text-xs text-white">{c.name}</span>
                    </button>
                  </div>)}
                </div>
                <p className="mt-3 border-t border-line/50 pt-2 text-[11px] text-muted">
                  #{row.a} + #{row.b} → #{row.result} · {row.source}
                </p>
              </article>)}
            </div>
            {!fusions?.rows.length&&<p className="text-sm text-muted">Nenhuma fusão identificada neste mod para a pesquisa atual.</p>}
          </section>}
          {(tab==="oponentes"||tab==="drops")&&<div className={panel+" space-y-3"}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-white">{tab==="oponentes"?"Deck dos oponentes":"Drops do adversário"}</h3>
              <select value={opponent} onChange={e=>setOpponent(Number(e.target.value))}
                className="rounded-lg border border-[#355878] bg-[#081930] px-3 py-2 text-sm">
                <option value={0}>Primeiro oponente</option>
                {opponents?.opponents.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
            <p className="text-xs text-[#abc0d8]">{tab==="oponentes"?opponents?.status:drops?.status}</p>
            {(tab==="oponentes"?opponents?.provisional:drops?.provisional)&&
              <p className="text-xs text-[#eec274]">Dados candidatos, ainda não confirmados em duelo.</p>}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {tab==="oponentes"?opponents?.cards.map(c=><button type="button" key={c.id}
                onClick={()=>setSelectedCard(cardsById.get(c.id)??null)}
                className="flex min-w-0 gap-3 rounded-xl border border-line/70 bg-[#0b1b34]/80 p-3 text-left hover:border-primary">
                <div className="w-20 shrink-0"><ImageFromPC token={token} sha={state.activeSha} card={cardsById.get(c.id)??null} compact/></div>
                <div className="min-w-0"><p className="text-xs text-gold">#{c.id}</p><p className="font-semibold text-white">{c.name}</p>
                  <p className="mt-2 text-xs text-primary">Peso: {c.weight}</p></div>
              </button>):
              drops?.rows.map((c,i)=><button type="button" key={c.cardId+"-"+i}
                onClick={()=>setSelectedCard(cardsById.get(c.cardId)??null)}
                className="flex min-w-0 gap-3 rounded-xl border border-line/70 bg-[#0b1b34]/80 p-3 text-left hover:border-primary">
                <div className="w-20 shrink-0"><ImageFromPC token={token} sha={state.activeSha} card={cardsById.get(c.cardId)??null} compact/></div>
                <div className="min-w-0"><p className="text-xs text-gold">#{c.cardId} · {c.groupLabel}</p>
                  <p className="font-semibold text-white">{c.cardName}</p>
                  <p className="text-xs text-primary">{value(c.chancePercent)}%</p></div>
              </button>)}
            </div>
          </div>}
                    {tab==="decks"&&<div className={panel+" space-y-4"}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-white">Deck e fusões do jogador</h3>
              <select value={deckId} onChange={e=>setDeckId(e.target.value)}
                className="max-w-full rounded-lg border border-[#355878] bg-[#081930] px-3 py-2 text-sm">
                <option value="">Deck ativo ou gravado</option>
                {decks?.saved.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <p className="text-xs text-[#adc1d8]">{decks?.status}</p>
            <p className="text-xs text-gold">{decks?.saveDisplayName}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {decks?.cards.map(c=><button type="button" key={c.id}
                onClick={()=>setSelectedCard(cardsById.get(c.id)??null)}
                className="flex min-w-0 gap-3 rounded-xl border border-line/70 bg-[#0b1b34]/80 p-3 text-left text-sm hover:border-primary">
                <div className="w-20 shrink-0"><ImageFromPC token={token} sha={state.activeSha} card={cardsById.get(c.id)??null} compact/></div>
                <div><p className="text-xs text-gold">#{c.id} · {c.count}x</p>
                  <p className="font-semibold text-white">{c.name}</p>
                  <p className="mt-2 text-xs text-muted">ATK {value(c.atk)} · DEF {value(c.def)}</p></div>
              </button>)}
            </div>
            <h4 className="font-semibold text-[#eabf69]">Fusões possíveis: {decks?.fusions.total??0}</h4>
            <div className="grid gap-2 md:grid-cols-2">
              {decks?.fusions.rows.slice(0,30).map((f,i)=><div key={i} className="rounded-lg border border-[#29496d] p-3 text-sm">
                {f.nameA} + {f.nameB} <strong className="text-[#eabf69]">= {f.nameResult}</strong>
              </div>)}
            </div>
          </div>}
          {tab==="inicio"&&<div className="grid gap-4 lg:grid-cols-2">
            <div className={panel+" space-y-3"}>
              <h3 className="font-semibold text-white">Mão ao vivo · ePSXe</h3>
              <p className="text-xs text-[#a3bdda]">{live?.hand.status||"Aguardando o emulador…"}</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {live?.hand.cards.map((c,i)=><button type="button" key={c.id+"-"+i}
                  onClick={()=>setSelectedCard(cardsById.get(c.id)??null)}
                  className="rounded-lg border border-line/70 bg-background/50 p-2 text-center text-sm hover:border-primary">
                  <p className="mb-2 text-xs text-gold">{c.slot}</p>
                  <ImageFromPC token={token} sha={state.activeSha} card={cardsById.get(c.id)??null} compact/>
                  <p className="mt-2 min-h-8 text-xs font-semibold text-white">{c.name}</p>
                  <p className="text-xs text-primary">ATK {value(c.atk)}</p>
                </button>)}
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
              <h3 className="font-semibold text-white">RANK ao vivo</h3>
              <div className="text-4xl font-bold text-[#eec579]">{live?.rank.category||"—"}</div>
              <p className="text-sm text-[#a3bdda]">Pontuação: {value(live?.rank.score)}</p>
              <p className="text-xs text-[#a3bdda]">{live?.rank.status||"Aguardando leitura local…"}</p>
            </div>
          </div>}
        </section>}
      </>}
      {selectedCard&&state?.activeSha&&<div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/85 p-3"
        role="presentation" onClick={()=>setSelectedCard(null)}>
        <section className="panel w-full max-w-2xl overflow-y-auto rounded-xl border-gold/50 p-5 shadow-2xl"
          role="dialog" aria-modal="true" aria-label={"Detalhes de "+selectedCard.name}
          onClick={e=>e.stopPropagation()}>
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="font-display text-xl font-bold text-gold">{selectedCard.name} · #{selectedCard.id}</h2>
            <button className="btn-ghost" type="button" onClick={()=>setSelectedCard(null)}>Fechar</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
            <ImageFromPC token={token} sha={state.activeSha} card={selectedCard}/>
            <div className="space-y-3">
              <p className="text-sm text-primary">ATK {value(selectedCard.atk)} · DEF {value(selectedCard.def)}</p>
              <p className="text-xs text-muted">{selectedCard.type||selectedCard.category}</p>
              <p className="whitespace-pre-wrap text-sm text-white">{selectedCard.description||"Descrição indisponível."}</p>
              {selectedCard.effect&&<p className="whitespace-pre-wrap text-sm text-primary">{selectedCard.effect}</p>}
            </div>
          </div>
        </section>
      </div>}
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-4 text-xs text-muted">
        <span className="flex items-center gap-2"><CloudOff className="size-4"/> ISO, Memory Card e RAM permanecem no PC</span>
        <span className="flex items-center gap-2"><ShieldCheck className="size-4"/> Conexão local autenticada</span>
        <span>Batoni Dev · DUELTRACE Cloud Alpha</span>
      </footer>
  </div>
}
