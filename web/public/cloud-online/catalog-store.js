/* DUELTRACE Cloud browser-only data store.
 * IndexedDB contains ONLY extracted user-selected catalogs, not ISO bytes.
 * No remote calls. Cross-device sync requires a separate authenticated backend.
 */
"use strict";
window.DueltraceCatalogStore = (() => {
  const DB="dueltrace-cloud-catalogs", VERSION=1;
  function open(){
    return new Promise((resolve,reject)=>{
      if(!("indexedDB" in window))return reject(Error("Este navegador não suporta salvar catálogos locais."));
      const req=indexedDB.open(DB,VERSION);
      req.onupgradeneeded=()=>{
        const db=req.result;
        if(!db.objectStoreNames.contains("mods"))db.createObjectStore("mods",{keyPath:"id"});
        if(!db.objectStoreNames.contains("settings"))db.createObjectStore("settings");
      };
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(Error("Não foi possível abrir o armazenamento local do navegador."));
      req.onblocked=()=>reject(Error("Feche outras guias DUELTRACE e tente novamente."));
    });
  }
  async function txRun(store,mode,action){
    const db=await open();
    try{
      return await new Promise((resolve,reject)=>{
        const tx=db.transaction(store,mode);
        const request=action(tx.objectStore(store));
        if(!request){reject(Error("Operação de dados inválida."));return;}
        request.onsuccess=()=>resolve(request.result);
        request.onerror=()=>reject(Error("Falha ao gravar catálogo no navegador."));
        tx.onabort=()=>reject(Error("Armazenamento do navegador indisponível."));
      });
    }finally{db.close();}
  }
  function normalize(obj){
    if(!obj||typeof obj!=="object"||obj.format!=="DUELTRACE-CLOUD-CATALOG"||obj.schema!==1)
      throw Error("JSON incompatível. Importe um catálogo exportado pelo DUELTRACE Cloud.");
    const cards=obj.cards;
    if(!Array.isArray(cards)||cards.length<1||cards.length>722)
      throw Error("Catálogo sem cartas ou acima de 722 registros.");
    const ids=new Set();
    const safe=cards.map(c=>{
      if(!c||!Number.isInteger(c.id)||c.id<1||c.id>722||ids.has(c.id))
        throw Error("ID da carta inválido ou duplicado.");
      ids.add(c.id);
      const name=String(c.name||"").trim().slice(0,120);
      if(!name)throw Error("Uma carta importada está sem nome.");
      const stat=x=>Number.isInteger(x)&&x>=0&&x<=5110?x:null;
      return {id:c.id,name,atk:stat(c.atk),def:stat(c.def),
        type:String(c.type||"Não identificado").slice(0,80),
        level:Number.isInteger(c.level)&&c.level>=0&&c.level<16?c.level:null,
        description:typeof c.description==="string"?c.description.slice(0,1800):null,
        effect:typeof c.effect==="string"?c.effect.slice(0,1800):null,
        evidence:String(c.evidence||"não_verificado").slice(0,90)};
    });
    const id=String(obj.id||obj.exeSha256||"").toLowerCase();
    if(!/^[a-f0-9]{64}$/.test(id))throw Error("Identificador SHA-256 do catálogo inválido.");
    const opponents=(Array.isArray(obj.opponents)?obj.opponents:[]).slice(0,39)
      .filter(o=>o&&Number.isInteger(o.id)&&o.id>=1&&o.id<=39)
      .map(o=>({id:o.id,name:String(o.name||"").slice(0,120)}));
    // Fusion/drop rows from an externally provided file are unverified data
    // until a future independent extractor and provenance validator exist.
    const fusions=(Array.isArray(obj.fusions)?obj.fusions:[]).slice(0,50000)
      .filter(f=>f&&[f.a,f.b,f.result].every(n=>Number.isInteger(n)&&n>=1&&n<=722))
      .map(f=>({a:f.a,b:f.b,result:f.result,source:"importado_não_verificado"}));
    const drops=(Array.isArray(obj.drops)?obj.drops:[]).slice(0,50000)
      .filter(d=>d&&Number.isInteger(d.cardId)&&d.cardId>=1&&d.cardId<=722)
      .map(d=>({cardId:d.cardId,opponentId:Number.isInteger(d.opponentId)?d.opponentId:null,
        groupLabel:String(d.groupLabel||"Não informado").slice(0,80),
        chancePercent:Number.isFinite(d.chancePercent)?Math.min(100,Math.max(0,d.chancePercent)):null,
        source:"importado_não_verificado"}));
    const warnings=(Array.isArray(obj.warnings)?obj.warnings:[]).slice(0,12)
      .map(x=>String(x).slice(0,220));
    return {schema:1,format:"DUELTRACE-CLOUD-CATALOG",id,
      sourceKind:String(obj.sourceKind||"json-importado").slice(0,64),
      name:String(obj.name||"Mod importado").slice(0,160),
      createdAt:String(obj.createdAt||new Date().toISOString()).slice(0,48),
      confidence:String(obj.confidence||"não_verificado").slice(0,80),
      exeSha256:id,cards:safe,opponents,fusions,drops,warnings};
  }
  async function save(input){
    const value=normalize(input);
    return txRun("mods","readwrite",store=>store.put(value)).then(()=>value);
  }
  const all=()=>txRun("mods","readonly",store=>store.getAll());
  const get=id=>txRun("mods","readonly",store=>store.get(id));
  const remove=id=>txRun("mods","readwrite",store=>store.delete(id));
  const getActive=()=>txRun("settings","readonly",store=>store.get("active"));
  const setActive=id=>txRun("settings","readwrite",store=>store.put(id,"active"));
  return Object.freeze({save,all,get,remove,getActive,setActive,normalize});
})();
