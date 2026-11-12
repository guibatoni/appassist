"use client"

/**
 * Local-first bridge: no hosted API requests for user ISOs, saves, cards or RAM.
 * Credentials remain in React state and are never persisted to browser storage.
 */
export const CONNECTOR_BASE = "http://127.0.0.1:8765"

export type CloudCard = {
  id:number;name:string;type:string|null;category:string|null;attribute:string|null
  atk:number|null;def:number|null;level:number|null
  effect:string|null;effectSource:string|null
  description:string|null;descriptionSource:string|null
}
export type CloudMod={
  sha256:string;name:string;cards:number;fusions:number
  opponents:number;dropEntries:number
}
export type CloudState={
  connected:boolean;storage:"local-only";cloudUpload:false
  activeSha:string|null;activeName:string
  mods:CloudMod[];cards:CloudCard[]
}
export type CloudFusion={a:number;b:number;result:number;nameA:string;nameB:string;nameResult:string;source:string;atk:number|null;def:number|null}
export type CloudFusionResult={total:number;offset:number;rows:CloudFusion[];provisional?:boolean}
export type CloudOpponentResult={
  available:boolean;status:string;opponentId:number;provisional?:boolean
  opponents:Array<{id:number;name:string}>
  cards:Array<{id:number;name:string;weight:number;chancePercent:number|null}>
}
export type CloudDropResult={
  available:boolean;status:string;provisional?:boolean
  total:number;rows:Array<{cardId:number;cardName:string;groupLabel:string;chancePercent:number|null;group?:string}>
}
export type CloudDeckResult={
  linked:boolean;status:string;cardName:string|null;saveDisplayName:string|null
  selectedBlock:number|null;gameIntegrityVerified:boolean;activeInEmulatorVerified:boolean
  cards:Array<{id:number;name:string;count:number;atk:number|null;def:number|null}>
  saved:Array<{id:string;name:string;source:string}>
  fusions:{total:number;rows:Array<{a:number;b:number;result:number;nameA:string;nameB:string;nameResult:string}>}
}
export type CloudLiveResult={
  localOnly:true
  hand:{ready:boolean;status:string;cards:Array<{id:number;slot:number;name:string;atk:number|null;def:number|null}>;pairs:Array<{slot_a:number;slot_b:number;result:number;result_name:string;atk:number|null;validation:string}>;chains:Array<{result:number;result_name:string;atk:number|null}>}
  rank:{ready?:boolean;state?:string;status?:string;category?:string|null;score?:number|null;rankSystem?:string|null}
}

async function request<T>(token:string,path:string,method:"GET"|"POST",body?:object):Promise<T>{
  if(!token||token.length<24)throw new Error("Informe a chave temporária do Connector.")
  if(!path.startsWith("/v1/")||path.startsWith("//"))throw new Error("Rota local inválida.")
  const response=await fetch(CONNECTOR_BASE+path,{
    method,cache:"no-store",mode:"cors",credentials:"omit",referrerPolicy:"no-referrer",
    headers:{
      Authorization:"Bearer "+token,
      ...(method==="POST"?{"Content-Type":"application/json"}:{}),
    },
    ...(method==="POST"?{body:JSON.stringify(body||{})}:{}),
  })
  if(!response.ok){
    const message=await response.json().catch(()=>({error:"Conector não disponível"}))
    throw new Error(typeof message.error==="string"?message.error:"Falha ao conectar")
  }
  return response.json() as Promise<T>
}
export function cloudGet<T>(token:string,path:string):Promise<T>{
  return request<T>(token,path,"GET")
}
export function cloudPost<T>(token:string,path:string,body:object):Promise<T>{
  return request<T>(token,path,"POST",body)
}
export async function cloudArt(token:string,sha:string,id:number):Promise<string>{
  if(!/^[a-f0-9]{64}$/.test(sha)||!Number.isInteger(id)||id<1||id>722){
    throw new Error("Carta inválida")
  }
  const response=await fetch(CONNECTOR_BASE+"/v1/art?sha="+sha+"&id="+id,{
    method:"GET",mode:"cors",cache:"no-store",credentials:"omit",
    referrerPolicy:"no-referrer",headers:{Authorization:"Bearer "+token},
  })
  if(!response.ok)throw new Error("Arte indisponível")
  const blob=await response.blob()
  if(blob.type!=="image/png"||blob.size>8_000_000)throw new Error("Imagem inválida")
  return URL.createObjectURL(blob)
}
