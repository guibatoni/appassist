/* DUELTRACE Cloud Web v0.7.0 — browser only. No connector, token,
 * localhost HTTP request, file upload or remote database requirement.
 * The installed website is hosted online; selected ISOs never leave the
 * browser. IndexedDB holds only derived catalogs and manual deck lists.
 */
"use strict";
(() => {
  const store=window.DueltraceCatalogStore;
  const scanner=window.DueltraceIsoScanner;
  const $=id=>document.getElementById(id);
  const panel=$("panel");
  let mods=[],active=null,tab="inicio",query="",page=0,detail=null;
  let hand=[],deck=[],loading=false;
  const node=(tag,cls="",text=null)=>{
    const e=document.createElement(tag);
    if(cls)e.className=cls;
    if(text!==null)e.textContent=String(text);
    return e;
  };
  const add=(parent,...children)=>{children.forEach(c=>{if(c!=null)parent.append(c);});return parent;};
  const btn=(text,fn,cls="")=>{const e=node("button",cls,text);e.type="button";e.addEventListener("click",fn);return e;};
  const section=title=>add(node("section","panel"),node("h2","",title));
  const p=(text,cls="muted")=>node("p",cls,text);
  const status=(message,error=false)=>{$("status").textContent=message;$("status").className=message?"notice visible"+(error?" error":""):"notice";};
  const stat=value=>typeof value==="number"?value.toLocaleString("pt-BR"):"—";
  const cardById=id=>active?.cards?.find(c=>c.id===id)||null;
  const cardName=id=>cardById(id)?.name||("#"+id);
  const showEmpty=(title,message)=>{const s=section(title);s.append(p(message));panel.append(s);};
  const activateTab=(next)=>{tab=next;page=0;query="";detail=null;void render();};
  const setLoading=busy=>{
    loading=busy;
    $("import-iso").disabled=busy;
    $("import-json").disabled=busy;
  };
  function rowTable(target,headers,rows){
    const wrap=node("div","table-scroll");
    const table=node("table"),thead=node("thead"),tr=node("tr");
    headers.forEach(h=>tr.append(node("th","",h)));
    thead.append(tr);table.append(thead);
    const tbody=node("tbody");
    rows.forEach(row=>{
      const tr=node("tr");
      row.forEach(value=>{
        const td=node("td");
        if(value instanceof Node)td.append(value);
        else td.textContent=String(value??"—");
        tr.append(td);
      });
      tbody.append(tr);
    });
    if(!rows.length){
      const tr=node("tr"),td=node("td","", "Nenhum registro validado disponível.");
      td.colSpan=headers.length;tr.append(td);tbody.append(tr);
    }
    table.append(tbody);wrap.append(table);target.append(wrap);
  }
  function cardButton(id,text=null){
    const card=cardById(id);
    return card?btn(text||card.name,()=>{detail=id;void render();},"rowlink"):node("span","",text||("#"+id));
  }
  async function sync(){
    mods=await store.all();
    const id=await store.getActive();
    active=mods.find(m=>m.id===id)||null;
    if(!active&&mods.length){active=mods[0];await store.setActive(active.id);}
    deck=active?(await store.getDeck(active.id)||[]):[];
    hand=[];
    await render();
  }
  async function imported(input){
    const value=await store.save(input);
    await store.setActive(value.id);
    await sync();
    tab="mods";
    await render();
    status("Catálogo importado e salvo neste navegador. A ISO original não foi enviada ao servidor.");
  }
  async function importISO(file){
    if(!file)return;
    setLoading(true);status("Lendo ISO/BIN no navegador, sem upload…");
    try{
      const data=await scanner.scan(file,message=>status(message));
      await imported(data);
      if(data.warnings?.length)status("Cartas extraídas do formato FM conhecido; fusões/drops e validação em jogo ainda não estão disponíveis.");
    }catch(e){status(e instanceof Error?e.message:"Não foi possível identificar a ISO/BIN.",true);}
    finally{setLoading(false);$("iso-file").value="";}
  }
  async function importJSON(file){
    if(!file)return;
    setLoading(true);status("Validando catálogo JSON…");
    try{
      if(file.size>6_000_000)throw Error("Catálogo JSON acima do limite de 6 MB.");
      const json=JSON.parse(await file.text());
      await imported(json);
    }catch(e){status(e instanceof Error?e.message:"Catálogo JSON inválido.",true);}
    finally{setLoading(false);$("catalog-file").value="";}
  }
  function exportCatalog(mod){
    // Optional export for moving data between devices without a server.
    const content=JSON.stringify(mod,null,2);
    const blob=new Blob([content],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=node("a");
    a.href=url;a.download="dueltrace-"+mod.id.slice(0,10)+".json";
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  async function activate(id){
    active=mods.find(m=>m.id===id)||null;
    await store.setActive(id);
    deck=await store.getDeck(id)||[];
    hand=[];
    status("Mod ativado neste navegador.");
    void render();
  }
  async function remove(id){
    const mod=mods.find(m=>m.id===id);
    if(!mod||!confirm("Excluir o catálogo \""+mod.name+"\" deste navegador? A ISO original não será afetada."))return;
    await store.remove(id);
    await sync();status("Catálogo removido deste navegador.");
  }
  function filterInput(parent,label,fn){
    const box=node("div","filterbar");
    const field=node("div");
    const input=node("input");input.type="search";input.value=query;input.placeholder="Digite nome ou ID";
    input.setAttribute("aria-label",label);
    input.addEventListener("input",()=>{query=input.value;page=0;fn(input.value);});
    add(field,node("label","",label),input);box.append(field);parent.append(box);
    return input;
  }
  function drawCards(parent,list){
    const grid=node("div","grid");
    list.forEach(c=>{
      const item=node("article","card");
      add(item,node("h3","", "#"+c.id+" · "+c.name),
        p("ATK "+stat(c.atk)+" · DEF "+stat(c.def),"stats"),
        p(c.type||"Tipo não identificado","muted small"));
      item.append(btn("Ver detalhes",()=>{detail=c.id;void render();}));
      grid.append(item);
    });
    parent.append(grid);
  }
  function showCard(id){
    const c=cardById(id);
    if(!c){showEmpty("Carta não encontrada","Não existe esta carta na ISO ativa.");return;}
    const s=section("#"+c.id+" · "+c.name);
    s.append(btn("← Voltar à biblioteca",()=>{detail=null;tab="biblioteca";void render();}));
    const grid=node("div","detail");
    const left=node("div");
    add(left,p("Arte não extraída pelo leitor web.","muted small"),
      p("Nenhuma imagem original é enviada à hospedagem.","muted small"));
    const right=node("div");
    add(right,p("ATK "+stat(c.atk)+" · DEF "+stat(c.def),"stats"),
      p("Tipo: "+(c.type||"Não identificado")),
      p("Nível: "+stat(c.level)),
      p(c.effect||c.description||"Efeito/descrição ainda não extraído para este mod."),
      p("Procedência: "+(c.evidence||"extração não verificada em jogo"),"muted small"));
    right.append(btn("Adicionar ao deck",()=>void addDeck(c.id),"gold"));
    if(hand.length<5)right.append(btn("Adicionar à mão manual",()=>{hand.push(c.id);tab="duelo";detail=null;void render();}));
    add(grid,left,right);s.append(grid);panel.append(s);
    const fusions=active.fusions||[];
    const material=fusions.filter(f=>f.a===id||f.b===id).slice(0,3);
    const produced=fusions.filter(f=>f.result===id).slice(0,Math.max(0,5-material.length));
    const hints=section("Fusões relacionadas (máximo de cinco dicas)");
    hints.append(p("As receitas importadas não são tratadas como confirmadas em jogo."));
    rowTable(hints,["Material 1","Material 2","Resultado"],[...material,...produced].map(f=>[
      cardButton(f.a),cardButton(f.b),cardButton(f.result)
    ]));
    panel.append(hints);
  }
  async function addDeck(id){
    if(!active)return;
    const current=deck.find(d=>d.id===id);
    const count=deck.reduce((sum,d)=>sum+d.count,0);
    if(count>=40){status("Limite sugerido de 40 cartas no deck manual.",true);return;}
    if(current){
      if(current.count>=3){status("Limite de 3 cópias por carta no deck manual.",true);return;}
      current.count++;
    }else deck.push({id,count:1});
    try{await store.saveDeck(active.id,deck);status("Carta adicionada ao deck deste navegador.");}
    catch(e){status(e.message,true);}
  }
  async function changeDeck(id,delta){
    const next=deck.map(d=>({...d}));
    const card=next.find(d=>d.id===id);
    if(!card)return;
    card.count+=delta;
    if(card.count<=0)next.splice(next.indexOf(card),1);
    if(card.count>3)return;
    await store.saveDeck(active.id,next);deck=next;
    void render();
  }
  function listMods(){
    const s=section("Biblioteca de Mods");
    s.append(p("Importe ISO/BIN diretamente pelo navegador. Nenhuma instalação, Connector ou upload do arquivo original."));
    s.append(p("Catálogos são armazenados neste navegador. Para acessar em outro aparelho, exporte o JSON e importe nele.","muted small"));
    if(!mods.length){
      s.append(p("Nenhum mod salvo. Escolha Importar ISO/BIN ou Importar catálogo JSON acima."));
    }else{
      const grid=node("div","grid");
      mods.forEach(m=>{
        const card=node("article","card");
        add(card,node("h3","",m.name),
          p(m.cards.length+" cartas · "+m.opponents.length+" oponentes · "+m.fusions.length+" fusões · "+m.drops.length+" drops","muted small"),
          p(m.sourceKind==="browser-iso-structural"?"Análise estrutural da ISO · não validada no jogo":"Catálogo importado · origem não verificada","muted small"));
        card.append(btn(active?.id===m.id?"Mod ativo":"Ativar mod",()=>void activate(m.id),active?.id===m.id?"":"gold"));
        card.append(btn("Exportar JSON",()=>exportCatalog(m)));
        card.append(btn("Excluir catálogo",()=>void remove(m.id)));
        grid.append(card);
      });
      s.append(grid);
    }
    panel.append(s);
  }
  function summary(){
    const s=section("DUELTRACE Cloud — independente do computador");
    s.append(p("O site funciona diretamente no navegador. Nenhuma chave, Connector, Python, Node.js ou aplicativo Windows é necessário."));
    s.append(p("Para consultar um mod, selecione uma ISO/BIN do seu dispositivo ou importe um catálogo JSON salvo anteriormente."));
    s.append(p("O arquivo do jogo não é enviado à Vercel. Apenas os registros extraídos são mantidos neste navegador.","muted small"));
    if(active){
      const grid=node("div","grid");
      [["Cartas",active.cards.length,"biblioteca"],["Fusões",active.fusions.length,"fusoes"],
       ["Oponentes",active.opponents.length,"oponentes"],["Drops",active.drops.length,"drops"]]
        .forEach(([name,count,dest])=>{
          const card=node("article","card");
          add(card,node("h3","",name),p(count+" registros","stats"),
            btn("Abrir",()=>activateTab(dest)));
          grid.append(card);
        });s.append(grid);
      if(active.warnings?.length){
        const warning=node("div","notice visible");
        warning.append(node("strong","", "Limitações da extração atual"));
        active.warnings.forEach(w=>warning.append(p(w,"muted small")));
        s.append(warning);
      }
    }else s.append(btn("Importar um mod",()=>{$("iso-file").click();},"gold"));
    panel.append(s);
  }
  function biblioteca(){
    const s=section("Biblioteca de Cartas");
    const inp=filterInput(s,"Buscar carta",()=>drawLibrary());
    const count=node("p","muted small");
    const results=node("div");
    const pagination=node("div","actions");
    add(s,count,results,pagination);panel.append(s);
    function drawLibrary(){
      const q=query.trim().toLowerCase();
      const match=active.cards.filter(c=>(c.id+" "+c.name+" "+c.type).toLowerCase().includes(q));
      count.textContent=match.length+" cartas encontradas";
      results.replaceChildren();pagination.replaceChildren();
      drawCards(results,match.slice(page*28,page*28+28));
      if(page)pagination.append(btn("← Anterior",()=>{page--;drawLibrary();}));
      if((page+1)*28<match.length)pagination.append(btn("Próxima →",()=>{page++;drawLibrary();}));
    }
    drawLibrary();
  }
  function fusionView(){
    const s=section("Fusões");
    s.append(p("Somente receitas existentes no catálogo importado; nenhuma combinação é inventada."));
    const recipes=active.fusions||[];
    if(!recipes.length){
      s.append(p("Nenhuma tabela de fusões validada foi extraída desta ISO. O leitor web inicial reconhece cartas e oponentes do layout FM; fusões de mods exigem um decodificador específico."));
    }else{
      const results=node("div");
      const draw=()=>{results.replaceChildren();
        const q=query.toLowerCase();
        const rows=recipes.filter(f=>[f.a,f.b,f.result,cardName(f.a),cardName(f.b),cardName(f.result)]
          .some(v=>String(v).toLowerCase().includes(q))).slice(0,250);
        rowTable(results,["Material 1","Material 2","Resultado"],rows.map(f=>
          [cardButton(f.a),cardButton(f.b),cardButton(f.result)]));
      };
      filterInput(s,"Buscar fusão",draw);
      s.append(p("Receitas importadas são provisórias até validação em jogo.","muted small"));
      s.append(results);draw();
    }
    panel.append(s);
  }
  function dropView(){
    const s=section("Drops");
    s.append(p("Dados de drops aparecem somente se o catálogo importado contiver registros identificados."));
    const rows=(active.drops||[]).slice(0,300);
    rowTable(s,["Oponente","Carta","Grupo","Chance"],rows.map(d=>
      [d.opponentId??"—",cardButton(d.cardId),d.groupLabel,stat(d.chancePercent)]));
    if(rows.length)s.append(p("Registros importados; probabilidades não verificadas individualmente no jogo.","muted small"));
    panel.append(s);
  }
  function opponentView(){
    const s=section("Oponentes");
    s.append(p("Nomes extraídos do executável somente quando o layout foi reconhecido."));
    rowTable(s,["ID","Oponente"],(active.opponents||[]).map(o=>[o.id,o.name]));
    panel.append(s);
  }
  function decks(){
    const s=section("Deck manual");
    const n=deck.reduce((a,b)=>a+b.count,0);
    s.append(p("Monte seu deck a partir da Biblioteca de Cartas. As escolhas são salvas neste navegador."));
    s.append(p(n+" / 40 cartas selecionadas","stats"));
    const rows=deck.map(d=>[cardButton(d.id),d.count,
      btn("−",()=>void changeDeck(d.id,-1)),btn("+",()=>void changeDeck(d.id,1))]);
    rowTable(s,["Carta","Qtd.","Remover","Adicionar"],rows);
    s.append(btn("Procurar cartas",()=>activateTab("biblioteca")));
    panel.append(s);
  }
  function duel(){
    const s=section("Duelo — simulação manual");
    s.append(p("Sem Connector, um site não pode ler a RAM do ePSXe instalado no Windows. Aqui você pode simular uma mão de cinco cartas manualmente."));
    const pick=node("div","filterbar");
    const field=node("div");
    field.append(node("label","","Adicionar carta à mão"));
    const input=node("input");input.placeholder="ID da carta (1 a 722)";input.type="number";
    input.min="1";input.max="722";field.append(input);
    pick.append(field);
    pick.append(btn("Adicionar",()=>{
      const id=Number(input.value);
      if(hand.length>=5||!cardById(id)){status("Escolha uma carta válida; a mão aceita cinco cartas.",true);return;}
      hand.push(id);status("");void render();
    },"gold"));
    s.append(pick);
    rowTable(s,["Posição","Carta","Ação"],hand.map((id,index)=>[
      index+1,cardButton(id),btn("Remover",()=>{hand.splice(index,1);void render();})
    ]));
    const recipes=(active.fusions||[]).filter(f=>hand.includes(f.a)&&hand.includes(f.b)).slice(0,5);
    s.append(node("h3","","Fusões possíveis da mão"));
    if(!recipes.length)s.append(p("Nenhuma receita correspondente disponível no catálogo; não podemos deduzir fusões sem os dados reais."));
    else rowTable(s,["Material 1","Material 2","Resultado"],recipes.map(f=>
      [cardButton(f.a),cardButton(f.b),cardButton(f.result)]));
    s.append(p("Leitura automática do duelo e RANK ao vivo exigirão um emulador executado no navegador e integração própria. Não estão ativos nesta versão.","muted small"));
    panel.append(s);
  }
  function settings(){
    const s=section("Configurações e privacidade");
    s.append(p("Cloud Web v0.7.0 — arquitetura sem Connector."));
    s.append(p("Os dados extraídos ficam em IndexedDB neste dispositivo, não em um banco de dados remoto. Isso permite usar o site sem aplicativo instalado, mas ainda não sincroniza seus catálogos automaticamente entre PC e celular."));
    s.append(p("Você pode exportar um catálogo JSON na Biblioteca de Mods e importá-lo em outro dispositivo."));
    s.append(p("Uma etapa futura de contas e banco de dados poderá oferecer sincronização com permissões e sem hospedar ISOs originais."));
    s.append(p("A importação binária atual extrai somente cartas e oponentes de layouts FM reconhecidos. Outros dados permanecem indisponíveis até verificação."));
    panel.append(s);
  }
  async function render(){
    $("active-mod").textContent=active?.name||"Nenhum mod importado";
    $("counts").textContent=active?active.cards.length+" cartas · "+active.opponents.length+
      " oponentes · "+(active.fusions||[]).length+" fusões":"Catálogo não carregado";
    document.querySelectorAll("[data-tab]").forEach(b=>b.classList.toggle("active",b.dataset.tab===tab));
    panel.replaceChildren();
    if(detail!==null){showCard(detail);return;}
    if(tab==="inicio"){summary();return;}
    if(tab==="mods"){listMods();return;}
    if(tab==="configuracoes"){settings();return;}
    if(!active){showEmpty("Nenhum catálogo ativo","Importe uma ISO/BIN pelo navegador para consultar cartas e oponentes.");return;}
    if(tab==="biblioteca")biblioteca();
    else if(tab==="fusoes")fusionView();
    else if(tab==="drops")dropView();
    else if(tab==="oponentes")opponentView();
    else if(tab==="decks")decks();
    else if(tab==="duelo")duel();
  }
  $("import-iso").addEventListener("click",()=>{if(!loading)$("iso-file").click();});
  $("iso-file").addEventListener("change",()=>void importISO($("iso-file").files?.[0]));
  $("import-json").addEventListener("click",()=>{if(!loading)$("catalog-file").click();});
  $("catalog-file").addEventListener("change",()=>void importJSON($("catalog-file").files?.[0]));
  document.querySelectorAll("[data-tab]").forEach(b=>b.addEventListener("click",()=>activateTab(b.dataset.tab)));
  if(!store||!scanner){status("Falha no carregamento do motor web. Atualize a página.",true);return;}
  sync().catch(e=>{status("O navegador não permitiu salvar os catálogos: "+e.message,true);void render();});
})();
