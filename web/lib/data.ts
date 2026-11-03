export type Attribute = "Água" | "Fogo" | "Terra" | "Vento" | "Sombra" | "Luz"
export type Rarity = "Comum" | "Rara" | "Épica" | "Lendária"
export type CardKind = "Monstro" | "Magia" | "Armadilha"

export type GameCard = {
  id: string
  name: string
  image: string
  attribute: Attribute
  type: string
  category: string
  kind: CardKind
  rarity: Rarity
  stars: number
  level: number
  atk: number
  def: number
  effect: string
}

const img = (name: string) => `/cards/${name}.png`

export const cards: GameCard[] = [
  { id: "c01", name: "Dragão Celeste", image: img("blue-dragon"), attribute: "Água", type: "Dragão", category: "Celestial", kind: "Monstro", rarity: "Lendária", stars: 5, level: 7, atk: 3000, def: 2500, effect: "Um dragão sagrado que domina os céus. Uma vez por turno, você pode destruir 1 carta no campo do oponente." },
  { id: "c02", name: "Dragão Flamejante", image: img("fire-dragon"), attribute: "Fogo", type: "Dragão", category: "Vulcânico", kind: "Monstro", rarity: "Épica", stars: 5, level: 7, atk: 2800, def: 2200, effect: "Quando invocado, causa 500 de dano aos pontos de vida do oponente." },
  { id: "c03", name: "Guardião de Pedra", image: img("stone-guardian"), attribute: "Terra", type: "Rocha", category: "Ancestral", kind: "Monstro", rarity: "Rara", stars: 4, level: 6, atk: 2000, def: 2800, effect: "Não pode ser destruído em batalha enquanto estiver em posição de defesa." },
  { id: "c04", name: "Águia dos Ventos", image: img("wind-eagle"), attribute: "Vento", type: "Besta Alada", category: "Celestial", kind: "Monstro", rarity: "Rara", stars: 4, level: 5, atk: 1900, def: 1400, effect: "Pode atacar diretamente se o oponente controlar apenas monstros de Terra." },
  { id: "c05", name: "Feiticeiro Sombrio", image: img("dark-mage"), attribute: "Sombra", type: "Mago", category: "Arcano", kind: "Monstro", rarity: "Épica", stars: 4, level: 6, atk: 2300, def: 2000, effect: "Uma vez por turno, compre 1 carta e descarte 1 carta da sua mão." },
  { id: "c06", name: "Arcanjo Dourado", image: img("light-angel"), attribute: "Luz", type: "Fada", category: "Sagrado", kind: "Monstro", rarity: "Lendária", stars: 5, level: 8, atk: 2900, def: 2600, effect: "Monstros de Luz que você controla ganham 300 de ATK." },
  { id: "c07", name: "Dragão Sombrio Supremo", image: img("dark-dragon"), attribute: "Sombra", type: "Dragão", category: "Abissal", kind: "Monstro", rarity: "Lendária", stars: 5, level: 8, atk: 3200, def: 2500, effect: "Resultado de fusão. Não pode ser alvo de efeitos de Magia do oponente." },
  { id: "c08", name: "Dragão de Gelo", image: img("ice-dragon"), attribute: "Água", type: "Dragão", category: "Glacial", kind: "Monstro", rarity: "Épica", stars: 4, level: 7, atk: 2600, def: 2300, effect: "Monstros que batalham com esta carta não podem mudar de posição no próximo turno." },
  { id: "c09", name: "Fênix Escarlate", image: img("fire-dragon"), attribute: "Fogo", type: "Besta Alada", category: "Vulcânico", kind: "Monstro", rarity: "Rara", stars: 4, level: 6, atk: 2200, def: 1600, effect: "Se for destruída, retorna ao campo na próxima fase de espera." },
  { id: "c10", name: "Cavaleiro do Trovão", image: img("thunder-knight"), attribute: "Luz", type: "Guerreiro", category: "Tempestade", kind: "Monstro", rarity: "Épica", stars: 4, level: 6, atk: 2400, def: 1900, effect: "Causa dano perfurante ao atacar um monstro em defesa." },
  { id: "c11", name: "Tornado Arcano", image: img("ice-dragon"), attribute: "Vento", type: "Magia", category: "Rápida", kind: "Magia", rarity: "Rara", stars: 4, level: 0, atk: 0, def: 0, effect: "Retorne 1 carta de Magia ou Armadilha do campo para a mão do dono." },
  { id: "c12", name: "Leão Solar", image: img("golden-lion"), attribute: "Luz", type: "Besta", category: "Sagrado", kind: "Monstro", rarity: "Rara", stars: 4, level: 5, atk: 2100, def: 1500, effect: "Ganha 500 de ATK durante o seu turno." },
  { id: "c13", name: "Lorde Abissal", image: img("dark-dragon"), attribute: "Sombra", type: "Demônio", category: "Abissal", kind: "Monstro", rarity: "Épica", stars: 4, level: 7, atk: 2700, def: 2100, effect: "Uma vez por turno, pode reduzir o ATK de 1 monstro do oponente pela metade." },
  { id: "c14", name: "Serpente Marinha", image: img("blue-dragon"), attribute: "Água", type: "Serpente Marinha", category: "Oceânico", kind: "Monstro", rarity: "Rara", stars: 4, level: 5, atk: 1800, def: 1700, effect: "Pode atacar duas vezes se houver uma carta de campo Oceano ativa." },
  { id: "c15", name: "Árvore Ancestral", image: img("ancient-tree"), attribute: "Terra", type: "Planta", category: "Ancestral", kind: "Monstro", rarity: "Rara", stars: 4, level: 5, atk: 1200, def: 2600, effect: "Recupera 300 pontos de vida durante cada fase de espera." },
  { id: "c16", name: "Ceifador das Sombras", image: img("dark-mage"), attribute: "Sombra", type: "Zumbi", category: "Arcano", kind: "Monstro", rarity: "Épica", stars: 4, level: 6, atk: 2400, def: 1800, effect: "Quando destrói um monstro, envie 1 carta aleatória da mão do oponente ao cemitério." },
  { id: "c17", name: "Serafim Radiante", image: img("light-angel"), attribute: "Luz", type: "Fada", category: "Sagrado", kind: "Monstro", rarity: "Épica", stars: 4, level: 6, atk: 2200, def: 2200, effect: "Uma vez por duelo, anule um ataque do oponente." },
  { id: "c18", name: "Wyrm Carmesim", image: img("fire-dragon"), attribute: "Fogo", type: "Dragão", category: "Vulcânico", kind: "Monstro", rarity: "Épica", stars: 4, level: 7, atk: 2600, def: 2000, effect: "Monstros de Fogo que você controla não podem ser destruídos por efeitos." },
  { id: "c19", name: "Paladino Glacial", image: img("thunder-knight"), attribute: "Água", type: "Guerreiro", category: "Glacial", kind: "Monstro", rarity: "Rara", stars: 4, level: 5, atk: 1900, def: 2000, effect: "Congela 1 monstro do oponente por um turno ao ser invocado." },
  { id: "c20", name: "Colosso Arenoso", image: img("stone-guardian"), attribute: "Terra", type: "Rocha", category: "Deserto", kind: "Monstro", rarity: "Rara", stars: 4, level: 6, atk: 1700, def: 2700, effect: "Ganha 200 de DEF para cada monstro de Terra no seu cemitério." },
  { id: "c21", name: "Fênix Áurea", image: img("phoenix"), attribute: "Luz", type: "Besta Alada", category: "Celestial", kind: "Monstro", rarity: "Lendária", stars: 5, level: 7, atk: 2700, def: 2300, effect: "Ao ser destruída, recupere 1000 pontos de vida." },
  { id: "c22", name: "Tita Sombrio de Pedra", image: img("dark-dragon"), attribute: "Terra", type: "Rocha", category: "Abissal", kind: "Monstro", rarity: "Épica", stars: 5, level: 8, atk: 3000, def: 2600, effect: "Resultado de fusão. Não pode ser destruído por efeitos de Armadilha." },
  { id: "c23", name: "Hiper Dragão Celeste", image: img("ice-dragon"), attribute: "Vento", type: "Dragão", category: "Celestial", kind: "Monstro", rarity: "Lendária", stars: 5, level: 8, atk: 3100, def: 2400, effect: "Resultado de fusão. Pode atacar todos os monstros do oponente uma vez cada." },
]

export const cardById = (id: string) => {
  const card = cards.find((c) => c.id === id)
  if (!card) throw new Error(`Carta não encontrada: ${id}`)
  return card
}

export const libraryCardIds = cards.slice(0, 21).map((c) => c.id)

export const recentCardIds = ["c01", "c13", "c03", "c14", "c04"]

export const collectionStats = {
  owned: 1842,
  total: 2100,
  favorites: 128,
  marked: 64,
  newCards: 12,
  breakdown: [
    { label: "Monstros", count: 1362, percent: 73.9, tone: "cyan" as const },
    { label: "Magias", count: 284, percent: 15.4, tone: "green" as const },
    { label: "Armadilhas", count: 196, percent: 10.6, tone: "purple" as const },
  ],
  totalPages: 37,
}

export const attributes: Attribute[] = ["Água", "Fogo", "Terra", "Vento", "Sombra", "Luz"]
export const cardKinds: CardKind[] = ["Monstro", "Magia", "Armadilha"]
export const categories = Array.from(new Set(cards.map((c) => c.category))).sort()

export type FusionRoute = {
  id: string
  label: string
  inputs: [string, string]
  result: string
  chance: number
  highlight?: boolean
}

export const fusionInputs = ["c01", "c03"]

export const alternativeRoutes: FusionRoute[] = [
  { id: "r1", label: "Rota Principal", inputs: ["c01", "c03"], result: "c07", chance: 100, highlight: true },
  { id: "r2", label: "Rota Elemental", inputs: ["c01", "c02"], result: "c13", chance: 88 },
  { id: "r3", label: "Rota Avançada", inputs: ["c01", "c04"], result: "c23", chance: 75 },
]

export const recommendedCombos = [
  { id: "k1", inputs: ["c01", "c03"] as [string, string], result: "c07", chance: 100, tag: "Melhor Escolha", tone: "gold" as const },
  { id: "k2", inputs: ["c05", "c03"] as [string, string], result: "c22", chance: 92, tag: "Alta Chance", tone: "green" as const },
  { id: "k3", inputs: ["c01", "c08"] as [string, string], result: "c23", chance: 85, tag: "Alternativa", tone: "muted" as const },
]

export const fusionHistory = [
  { id: "h1", date: "Hoje 14:27", inputs: ["c01", "c03"] as [string, string], result: "c07", status: "Sucesso" },
  { id: "h2", date: "Hoje 13:11", inputs: ["c13", "c03"] as [string, string], result: "c22", status: "Sucesso" },
  { id: "h3", date: "Ontem 22:48", inputs: ["c01", "c04"] as [string, string], result: "c23", status: "Sucesso" },
]

export const comparisonIds = ["c07", "c22", "c23"]

export const fusionChecks = [
  "Requisitos de Nível: OK",
  "Atributos Compatíveis: OK",
  "Tipo de Fusão: Padrão",
  "Resultado Encontrado: 1 carta",
]

export const diagnostics = [
  { label: "Dados da Fusão", value: "OK" },
  { label: "Compatibilidade", value: "OK" },
  { label: "Banco de Rotas", value: "Atualizado" },
]
