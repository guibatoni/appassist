"use client"

import { useState } from "react"
import { ChevronsRight, CircleCheck, Crown, FileText, FlaskConical, Infinity as InfinityIcon, Plus, RotateCcw, Scale, Star, Swords, Users, X } from "lucide-react"
import { cardById, fusionChecks, fusionInputs } from "@/lib/data"
import { AttributeIcon, GameCardArt } from "@/components/ui/game-card"
import { ProgressBar } from "@/components/ui/panel"

export function FusionAnalysis() {
  const [inputs, setInputs] = useState<string[]>(fusionInputs)
  const result = cardById("c07")
  const valid = inputs.length >= 2
  const chance = valid ? 100 : 0

  return (
    <section className="panel" aria-labelledby="analise-fusao">
      <div className="flex flex-wrap items-center gap-3 border-b border-line/50 px-4 py-2.5">
        <h2 id="analise-fusao" className="flex items-center gap-2 font-display text-xl font-bold text-white">
          <InfinityIcon className="size-6 text-gold" aria-hidden="true" />
          Análise de Fusão
        </h2>
        <p className="text-sm text-foreground/80">Selecione duas ou mais cartas para analisar a fusão, rotas alternativas e chances de sucesso.</p>
        <div className="ml-auto flex gap-2">
          <button type="button" className="btn-ghost py-1.5" onClick={() => setInputs([])}>
            <RotateCcw className="size-4" aria-hidden="true" /> Limpar
          </button>
          <button type="button" className="btn-ghost py-1.5">
            <Star className="size-4" aria-hidden="true" /> Salvar Análise
          </button>
        </div>
      </div>

      <div className="grid gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_260px]">
        <div className="rounded-lg border border-line/60 bg-[#06122b]/70 p-2.5">
          <h3 className="mb-2 flex items-center gap-2 font-display text-sm font-semibold text-white">
            <Users className="size-4 text-primary" aria-hidden="true" /> Cartas de Entrada (Fusão)
          </h3>
          <ul className="flex flex-col gap-2">
            {inputs.map((id) => {
              const card = cardById(id)
              return (
                <li key={id} className="flex items-center gap-3 rounded-md border border-line/60 bg-panel-strong/60 p-1.5 transition-colors hover:border-primary/60">
                  <GameCardArt card={card} size="sm" className="w-16" />
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="truncate font-semibold text-white">{card.name}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-foreground/85"><AttributeIcon attribute={card.attribute} className="size-4" /> {card.attribute}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-foreground/85"><Star className="size-4 fill-gold text-gold" aria-hidden="true" /> Nível: {card.level}</p>
                  </div>
                  <button type="button" onClick={() => setInputs((p) => p.filter((x) => x !== id))} className="self-start rounded border border-line p-0.5 text-foreground/80 hover:border-danger hover:text-danger" aria-label={`Remover ${card.name}`}>
                    <X className="size-4" />
                  </button>
                </li>
              )
            })}
            <li>
              <button
                type="button"
                onClick={() => setInputs((p) => (p.length ? p : fusionInputs))}
                className="flex w-full items-center justify-center gap-3 rounded-md border border-dashed border-line px-3 py-2 text-sm text-foreground/90 transition-colors hover:border-primary hover:text-white"
              >
                <Plus className="size-6" aria-hidden="true" />
                <span className="text-left leading-tight">Adicionar Carta<br /><span className="text-xs text-muted">(2 ou mais)</span></span>
              </button>
            </li>
          </ul>
        </div>

        <div className="flex flex-col rounded-lg border border-line/60 bg-[#06122b]/70 p-2.5">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 font-display text-sm font-semibold text-white">
              <Crown className="size-4 text-gold" aria-hidden="true" /> Rota de Fusão Principal
            </h3>
            <span className="inline-flex items-center gap-1 rounded border border-gold/70 bg-gold/15 px-3 py-0.5 text-xs font-semibold text-gold">
              <Star className="size-3 fill-gold" aria-hidden="true" /> Rota Recomendada
            </span>
          </div>

          <div className="flex flex-1 flex-col items-center justify-center gap-4 py-3 sm:flex-row sm:gap-6">
            <div className="flex flex-col items-center">
              <div className="flex items-center gap-3">
                {inputs.slice(0, 2).map((id, i) => (
                  <div key={id} className="flex items-center gap-3">
                    {i > 0 && <Plus className="size-7 text-white" aria-hidden="true" />}
                    <GameCardArt card={cardById(id)} className="w-20 sm:w-[88px]" />
                  </div>
                ))}
              </div>
              <svg viewBox="0 0 120 24" className="h-6 w-32 text-primary" aria-hidden="true">
                <path d="M20 0v10h80V0M60 10v12" fill="none" stroke="currentColor" strokeWidth="2.5" />
                <path d="M54 16l6 7 6-7" fill="none" stroke="currentColor" strokeWidth="2.5" />
              </svg>
            </div>
            <ChevronsRight className="size-10 rotate-90 text-primary drop-shadow-[0_0_8px_rgb(56_200_255/0.9)] sm:rotate-0" aria-hidden="true" />
            <div className="relative">
              <div className="absolute -inset-6 rounded-full bg-violet/20 blur-2xl" aria-hidden="true" />
              <GameCardArt card={result} size="lg" className="relative w-28 ring-2 ring-violet shadow-[0_0_28px_rgb(163_92_245/0.8)] sm:w-32" />
            </div>
            <div className="text-sm">
              <p className="font-display text-lg font-bold text-white">{result.name}</p>
              <p className="mt-2 flex items-center gap-2 text-foreground/90"><AttributeIcon attribute={result.attribute} className="size-5" /> {result.attribute}</p>
              <p className="mt-1.5 flex items-center gap-2 text-foreground/90"><Star className="size-5 fill-gold text-gold" aria-hidden="true" /> Nível: {result.level}</p>
              <p className="mt-1.5 flex gap-4 text-white">
                <span>ATK: {result.atk}</span>
                <span>DEF: {result.def}</span>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <button type="button" className="btn-gold"><FlaskConical className="size-4" aria-hidden="true" /> Analisar Rotas</button>
            <button type="button" className="btn-ghost"><FileText className="size-4" aria-hidden="true" /> Ver Detalhes</button>
            <button type="button" className="btn-ghost"><Scale className="size-4" aria-hidden="true" /> Comparar Cartas</button>
            <button type="button" className="btn-ghost"><Swords className="size-4" aria-hidden="true" /> Simular Duelo</button>
          </div>
        </div>

        <div className="rounded-lg border border-line/60 bg-[#06122b]/70 p-2.5 lg:col-span-2 xl:col-span-1">
          <h3 className="mb-2 flex items-center gap-2 font-display text-sm font-semibold text-white">
            <CircleCheck className="size-4 text-primary" aria-hidden="true" /> Validade da Fusão
          </h3>
          <p className={valid
            ? "flex items-center justify-center gap-2 rounded-md border border-success/70 bg-success/20 py-1.5 font-display text-lg font-bold text-success shadow-[0_0_14px_rgb(47_210_122/0.35)]"
            : "flex items-center justify-center gap-2 rounded-md border border-danger/70 bg-danger/15 py-1.5 font-display text-lg font-bold text-danger"}>
            <CircleCheck className="size-5" aria-hidden="true" /> {valid ? "Fusão Válida" : "Selecione 2 cartas"}
          </p>
          <div className="mt-3 flex items-end justify-between">
            <span className="text-sm text-white">Chance de Sucesso</span>
            <span className="font-display text-3xl font-bold text-success">{chance}%</span>
          </div>
          <ProgressBar value={chance} tone="green" segmented className="mt-1.5 h-3" />
          <ul className="mt-3 flex flex-col gap-1.5 text-sm text-foreground/95">
            {fusionChecks.map((c) => (
              <li key={c} className="flex items-center gap-2">
                <CircleCheck className="size-4 text-success" aria-hidden="true" /> {c}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
