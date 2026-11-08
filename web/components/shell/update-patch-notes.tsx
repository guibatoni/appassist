"use client"

import {useEffect,useRef} from "react"
import {createPortal} from "react-dom"
import {BookOpen,CheckCircle2,X} from "lucide-react"
import type {UpdateNoteGroup} from "@/lib/desktop"

type Props={
  open:boolean
  onClose:()=>void
  version:string
  notes:UpdateNoteGroup[]
}

/** Modal local: não navega para o GitHub e não interpreta Markdown/HTML remoto. */
export function UpdatePatchNotes({open,onClose,version,notes}:Props){
  const dialogRef=useRef<HTMLDivElement>(null)
  const closeRef=useRef<HTMLButtonElement>(null)

  useEffect(()=>{
    if(!open)return
    const previous=document.activeElement instanceof HTMLElement ?
      document.activeElement : null
    const originalOverflow=document.body.style.overflow
    document.body.style.overflow="hidden"
    closeRef.current?.focus()
    const onKey=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();onClose();return}
      if(event.key!=="Tab"||!dialogRef.current)return
      const controls=Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'))
      if(!controls.length)return
      const first=controls[0],last=controls[controls.length-1]
      if(event.shiftKey&&document.activeElement===first){
        event.preventDefault();last.focus()
      }else if(!event.shiftKey&&document.activeElement===last){
        event.preventDefault();first.focus()
      }
    }
    document.addEventListener("keydown",onKey)
    return()=>{
      document.removeEventListener("keydown",onKey)
      document.body.style.overflow=originalOverflow
      previous?.focus()
    }
  },[open,onClose])

  if(!open||typeof document==="undefined")return null
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#020714]/80 px-4 py-6 backdrop-blur-md"
      onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
      <div ref={dialogRef} role="dialog" aria-modal="true"
        aria-labelledby="patch-notes-title" aria-describedby="patch-notes-subtitle"
        className="flex max-h-[min(85vh,720px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-gold/40 bg-[#0b1930] shadow-[0_24px_90px_rgba(0,0,0,.75)]">
        <header className="flex items-start justify-between gap-4 border-b border-line/70 px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="rounded-xl bg-gold/10 p-2 text-gold"><BookOpen className="size-5"/></span>
            <div>
              <h2 id="patch-notes-title" className="font-display text-lg font-semibold text-gold">
                Patch notes
              </h2>
              <p id="patch-notes-subtitle" className="mt-1 text-xs text-muted">
                {version ? `DUELTRACE v${version}` : "Novidades do DUELTRACE"}
              </p>
            </div>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Fechar patch notes"
            className="rounded-lg p-2 text-muted transition-colors hover:bg-white/10 hover:text-white">
            <X className="size-4"/>
          </button>
        </header>
        <div className="space-y-5 overflow-y-auto px-5 py-5 text-sm">
          {notes.length>0?notes.map(group=>
            <section key={group.title} aria-label={group.title}>
              <h3 className="mb-2 font-semibold text-primary">{group.title}</h3>
              <ul className="space-y-2">
                {group.items.map((item,index)=>
                  <li key={index} className="flex gap-2 leading-relaxed text-foreground/90">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gold/80"/>
                    <span>{item}</span>
                  </li>)}
              </ul>
            </section>):
            <p className="rounded-lg border border-line/70 bg-background/40 px-4 py-3 text-muted">
              As novidades desta versão ainda não foram publicadas.
            </p>}
        </div>
        <footer className="flex justify-end border-t border-line/70 px-5 py-3">
          <button type="button" className="btn-gold rounded-lg px-5 py-2 text-xs font-semibold"
            onClick={onClose}>Fechar</button>
        </footer>
      </div>
    </div>,document.body)
}
