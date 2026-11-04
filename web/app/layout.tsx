import type { Metadata, Viewport } from "next"
import localFont from "next/font/local"
import "./globals.css"
import { AppShell } from "@/components/shell/app-shell"

const geistSans = localFont({
  src: "./fonts/Geist-Variable.ttf",
  variable: "--font-geist-sans",
  weight: "100 900",
  style: "normal",
  display: "swap",
})
const exo = localFont({
  src: "./fonts/Exo2-Variable.ttf",
  variable: "--font-exo",
  weight: "100 900",
  style: "normal",
  display: "swap",
})

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
