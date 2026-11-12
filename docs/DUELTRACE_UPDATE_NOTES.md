# DUELTRACE v0.17.3 — Preview

## Novidades
- O Memory Card agora mantém a escolha do save por SHA-256 da ISO ativa, inclusive após reiniciar o DUELTRACE.
- Selecionar o Bloco 4 do mod Rising of Wicked Gods permanece uma preferência específica daquele mod; nenhuma outra ISO herda essa seleção.
- Confirmação visual discreta do bloco de save memorizado na aba Decks.

## Melhorias
- Ao selecionar novamente o mesmo Memory Card, o DUELTRACE conserva o bloco escolhido e a identidade da partida.
- A sequência de gravação (por exemplo, 3 → 4) pode avançar sem perder a referência do save escolhido.
- Compatibilidade com preferências de bloco gravadas pelas versões anteriores.

## Correções
- Um bloco temporariamente ausente ou substituído por outra partida não provoca a seleção silenciosa de outro deck.
- A identidade do save é conferida pelo nome interno e código de duelista; nunca pela sequência de salvamento isoladamente.
- O Memory Card original, os snapshots, o catálogo de mods e o executável do emulador não são alterados.
