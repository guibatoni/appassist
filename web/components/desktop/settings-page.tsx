"use client"

import {useState} from "react"
import {CheckCircle2,Globe2,Monitor,ShieldAlert,Settings2} from "lucide-react"
import {LOCALES,useI18n,T,type AppLocale} from "@/lib/i18n"

export function SettingsPage() {
  const {locale,setLocale,ready,t}=useI18n()
  const [busy,setBusy]=useState(false)
  const [status,setStatus]=useState<"saved"|"error"|null>(null)
  const change=async(next:AppLocale)=>{
    if(busy||next===locale)return
    setBusy(true);setStatus(null)
    try{
      await setLocale(next)
      setStatus("saved")
    }catch{
      setStatus("error")
    }finally{setBusy(false)}
  }
  return <div className="flex flex-col gap-4">
    <header className="panel rounded-xl border-gold/45 bg-gradient-to-r from-[#142b51] to-[#061126] p-4">
      <div className="flex items-center gap-3">
        <Settings2 className="size-7 shrink-0 text-gold"/>
        <div>
          <h1 className="font-display text-2xl font-semibold text-gold"><T k="Configurações"/></h1>
          <p className="text-sm text-muted"><T k="As configurações ficam salvas localmente no computador."/></p>
        </div>
      </div>
    </header>
    <section className="panel rounded-xl p-4 sm:p-5">
      <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-white">
        <Globe2 className="size-5 text-primary"/><T k="Linguagem do aplicativo"/>
      </h2>
      <label className="flex max-w-xl flex-col gap-2 text-sm text-muted" htmlFor="dueltrace-ui-language">
        <T k="Idioma"/>
        <select id="dueltrace-ui-language" className="field w-full px-3 py-3 text-white"
          disabled={!ready||busy} value={locale}
          onChange={event=>void change(event.target.value as AppLocale)}>
          {LOCALES.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
      </label>
      <p className="mt-3 text-xs text-muted"><T k="O idioma é aplicado imediatamente e salvo para a próxima abertura."/></p>
      {busy&&<p role="status" className="mt-2 text-sm text-primary"><T k="Salvando preferência…"/></p>}
      {status==="saved"&&<p role="status" className="mt-2 flex items-center gap-2 text-sm text-primary">
        <CheckCircle2 className="size-4"/><T k="Preferência salva automaticamente."/>
      </p>}
      {status==="error"&&<p role="alert" className="mt-2 text-sm text-red-300">
        <T k="Não foi possível salvar. Tente novamente."/>
      </p>}
    </section>
    <section className="panel rounded-xl p-4 sm:p-5">
      <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-white">
        <Monitor className="size-5 text-primary"/><T k="Aparência e janela"/>
      </h2>
      <p className="mt-3 font-semibold text-foreground"><T k="Salvar tamanho e posição da janela"/></p>
      <p className="mt-1 text-sm text-muted"><T k="O DUELTRACE restaura o último tamanho e posição válidos ao iniciar."/></p>
      <p className="mt-2 text-xs text-primary"><T k="Preferência salva automaticamente."/></p>
    </section>
    <section className="panel rounded-xl border-gold/35 p-4 sm:p-5">
      <h2 className="font-display text-lg font-semibold text-gold"><T k="Créditos"/></h2>
      <p className="mt-3 text-sm text-muted"><T k="Desenvolvido por"/></p>
      <p className="mt-1 text-lg font-bold text-white"><T k="Batoni Dev - Guilherme Batoni"/></p>
      <div className="mt-5 rounded-lg border border-gold/30 bg-[#0a142a] p-3">
        <p className="flex items-center gap-2 font-semibold text-gold">
          <ShieldAlert className="size-5"/><T k="Direitos de uso"/>
        </p>
        <p className="mt-2 font-semibold text-white"><T k="Não permitida a distribuição do aplicativo."/></p>
        <p className="mt-1 text-sm text-muted">
          <T k="É proibido redistribuir, republicar ou disponibilizar cópias do DUELTRACE sem autorização expressa do desenvolvedor."/>
        </p>
      </div>
      <p className="mt-4 text-xs text-muted"><T k="© Batoni Dev. Todos os direitos reservados."/></p>
    </section>
  </div>
}
