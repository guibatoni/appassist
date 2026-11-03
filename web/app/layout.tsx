import type { Metadata, Viewport } from "next"
import { Geist, Exo_2 } from "next/font/google"
import "./globals.css"
import { AppShell } from "@/components/shell/app-shell"

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] })
const exo = Exo_2({ variable: "--font-exo", subsets: ["latin"], weight: ["500", "600", "700", "800"] })

export const metadata: Metadata = {
  title: "DUELTRACE — MultiMod Companion",
  description: "Biblioteca de cartas, análise de fusões e overlay de duelo para Yu-Gi-Oh! Forbidden Memories e mods.",
}

export const viewport: Viewport = {
  themeColor: "#040a1a",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${exo.variable} antialiased`}>
      <body className="min-h-dvh font-sans">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
