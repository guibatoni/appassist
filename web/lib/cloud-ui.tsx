"use client"

import {createContext,useContext,useMemo,useState} from "react"

export type CloudTab="inicio"|"mods"|"biblioteca"|"fusoes"|"drops"|"oponentes"|"decks"|"configuracoes"
export const CLOUD_NAV:ReadonlyArray<{id:CloudTab,label:string}>=[
  {id:"inicio",label:"Início"},
  {id:"mods",label:"Biblioteca de Mods"},
  {id:"biblioteca",label:"Biblioteca de Cartas"},
  {id:"fusoes",label:"Fusões"},
  {id:"drops",label:"Drops"},
  {id:"oponentes",label:"Oponentes"},
  {id:"decks",label:"Decks"},
  {id:"configuracoes",label:"Configurações"},
]

type CloudUiState={
  tab:CloudTab
  setTab:(tab:CloudTab)=>void
  connected:boolean
  setConnected:(connected:boolean)=>void
}
const Ctx=createContext<CloudUiState|null>(null)
export function CloudUiProvider({children}:{children:React.ReactNode}){
  const [tab,setTab]=useState<CloudTab>("inicio")
  const [connected,setConnected]=useState(false)
  const value=useMemo(()=>({tab,setTab,connected,setConnected}),[tab,connected])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export function useCloudUi(){
  const ctx=useContext(Ctx)
  if(!ctx)throw new Error("DUELTRACE Cloud layout unavailable")
  return ctx
}
