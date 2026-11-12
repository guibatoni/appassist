"use client"

import {createContext, useCallback, useContext, useEffect, useMemo, useState} from "react"
import {desktopApi} from "@/lib/desktop"
import {CORE_TRANSLATIONS} from "./i18n-core"
import {EXTRA_TRANSLATIONS} from "./i18n-extra"
import {DETAIL_TRANSLATIONS} from "./i18n-details"

export type AppLocale="pt-BR"|"en"|"es"|"ja"|"zh-CN"|"it"
export const LOCALES:ReadonlyArray<{code:AppLocale;name:string}>= [
  {code:"pt-BR",name:"Português (Brasil)"},
  {code:"en",name:"English"},
  {code:"es",name:"Español"},
  {code:"ja",name:"日本語"},
  {code:"zh-CN",name:"简体中文"},
  {code:"it",name:"Italiano"},
]
const AVAILABLE:ReadonlyArray<AppLocale>=LOCALES.map(v=>v.code)
export const DICTIONARY:Record<string,Record<string,string>>={
  ...CORE_TRANSLATIONS,...EXTRA_TRANSLATIONS,...DETAIL_TRANSLATIONS,
}
export function translate(key:string,locale:AppLocale):string {
  if(locale==="pt-BR")return key
  return DICTIONARY[key]?.[locale]??key
}
type LanguageContext={
  locale:AppLocale
  ready:boolean
  t:(key:string)=>string
  setLocale:(next:AppLocale)=>Promise<void>
}
const Context=createContext<LanguageContext>({
  locale:"pt-BR",ready:false,
  t:(key)=>key,setLocale:async()=>{},
})
export function I18nProvider({children}:{children:React.ReactNode}) {
  const [locale,setCurrent]=useState<AppLocale>("pt-BR")
  const [ready,setReady]=useState(false)
  useEffect(()=>{
    let mounted=true,attempts=0
    const probe=()=>{
      const api=desktopApi()
      if(!api){
        if(++attempts<30) return
        if(mounted)setReady(true)
        return
      }
      void api.get_ui_settings().then(settings=>{
        if(!mounted)return
        if(AVAILABLE.includes(settings.language as AppLocale)){
          setCurrent(settings.language as AppLocale)
        }
      }).catch(()=>{}).finally(()=>{if(mounted)setReady(true)})
      return true
    }
    if(probe())return()=>{mounted=false}
    const timer=window.setInterval(()=>{
      if(probe())window.clearInterval(timer)
    },450)
    const onReady=()=>{if(probe())window.clearInterval(timer)}
    window.addEventListener("pywebviewready",onReady)
    return()=>{mounted=false;window.clearInterval(timer)
      window.removeEventListener("pywebviewready",onReady)}
  },[])
  useEffect(()=>{
    document.documentElement.lang=locale
  },[locale])
  const setLocale=useCallback(async(next:AppLocale)=>{
    if(!AVAILABLE.includes(next))throw new Error("Unsupported locale")
    const api=desktopApi()
    if(!api)throw new Error("DUELTRACE Windows API unavailable")
    const response=await api.set_ui_language(next)
    if(response.language!==next)throw new Error("Language not confirmed")
    setCurrent(next)
  },[])
  const t=useCallback((key:string)=>translate(key,locale),[locale])
  const state=useMemo(()=>({locale,ready,t,setLocale}),[locale,ready,t,setLocale])
  return <Context.Provider value={state}>{children}</Context.Provider>
}
export const useI18n=()=>useContext(Context)
export function T({k}:{k:string}){
  const {t}=useI18n()
  return <>{t(k)}</>
}
