export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ")
}

export function formatNumber(value: number) {
  return value.toLocaleString("pt-BR")
}
