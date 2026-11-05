import Image from "next/image"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"

export function AppShell({ children }: { children: React.ReactNode }) {
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

      <div className="dueltrace-scroll relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto max-w-[1600px] p-2 sm:p-4 lg:p-6">
          <div className="frame-glow relative rounded-2xl border border-gold/40 bg-[#040b1f]/90 backdrop-blur-sm">
            <TopBar />
            <div className="flex flex-col gap-3 px-3 pb-4 sm:px-4 lg:flex-row lg:gap-4 lg:pb-5">
              <Sidebar />
              <main className="min-w-0 flex-1">{children}</main>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
