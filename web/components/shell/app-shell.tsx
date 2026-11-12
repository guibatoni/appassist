"use client"

import {usePathname} from "next/navigation"
import Image from "next/image"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import {I18nProvider} from "@/lib/i18n"

function ShellBody({ children }: { children: React.ReactNode }) {
  const route=usePathname()
  if(route.startsWith("/ferramentas/")){
    // Small native pywebview window: no main sidebar or window toolbar.
    return <div className="dueltrace-scroll h-dvh overflow-y-auto bg-background p-3">{children}</div>
  }
  return (
    <div className="relative flex h-dvh min-h-0 flex-col overflow-hidden">
      <Image
        src="/bg-temple.png"
        alt=""
        fill
        priority
        sizes="100vw"
        className="pointer-events-none -z-10 object-cover opacity-70"
      />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,rgb(4_10_26/0.55),rgb(4_10_26/0.92))]" />

      <div className="dueltrace-scroll relative z-10 min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
        <div className="dt-app-padding mx-auto w-full max-w-[2100px] p-2 sm:p-3 xl:p-5 2xl:p-6">
          <div className="frame-glow relative min-w-0 rounded-2xl border border-gold/40 bg-[#040b1f]/90 backdrop-blur-sm">
            <TopBar />
            <div className="dt-shell-body flex min-w-0 flex-col gap-3 px-2 pb-3 sm:px-4 lg:flex-row lg:gap-4 lg:pb-5">
              <Sidebar />
              <main className="dueltrace-main min-w-0 flex-1">{children}</main>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function AppShell({children}:{children:React.ReactNode}) {
  return <I18nProvider><ShellBody>{children}</ShellBody></I18nProvider>
}
