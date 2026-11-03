# DUELTRACE Alpha v0.6.4 — Mão ao vivo na aba Início

## O que mudou
A aba **Início** substitui os painéis estáticos por uma central de duelo:

- **5 cartas da mão**: posição, ID, nome e ATK/DEF do perfil ativo; mostra PNG extraído localmente quando presente, ou símbolo gráfico.
- **Fusões possíveis**: combinações entre dois slots distintos da mão, usando SOMENTE as receitas já disponíveis no perfil ativo. Lista ordenada por maior ATK do resultado e indica proveniência: `ISO ×7` (extração estrutural), `Testada` (receita individual registrada como observada em duelo) e `Revisada`.
- **Atualização automática** enquanto Início está aberta; botão **Atualizar mão** para nova leitura imediata.
- Leitura RAM por processo `ePSXe.exe` a cada ~1,1 segundo, com uma thread pequena e atualização segura pela fila do Tk.
- **Sem adivinhação:** se o ePSXe estiver fechado, o acesso à RAM for negado ou os cinco slots falharem na validação, as cartas e sugestões são apagadas.

## Como usar
1. Execute a nova Alpha Windows, sem CMD.
2. Em Biblioteca de Mods, selecione a ISO e clique **Ativar perfil**.
3. Inicie o ePSXe pela integração configurada, ou abra seu ePSXe de forma normal.
4. Entre em um duelo para que o jogo mantenha cinco cartas válidas na mão.
5. Volte à aba **Início**: as cinco cartas e as fusões disponíveis devem aparecer automaticamente.
6. As cartas são vinculadas ao **perfil escolhido**; o aplicativo ainda não confirma de forma independente qual ISO o ePSXe abriu. Confirme que você selecionou o mod correto.

## Detalhes de memória e validação
A janela de leitura é `0xBFF484`, com **140 bytes** (5 slots de 28). Para cada slot, o programa verifica ID `1..722` e índice de posição de `uint32` no deslocamento +12. Essa validação replica `fusion_ram_probe.decode_hand` e se baseia na experiência anterior do painel clássico. A leitura é só uma inspeção, sem escrita nem modificações do jogo.

O processo é descoberto por nome e, quando o DUELTRACE iniciou o ePSXe, prefere o PID correspondente. Com múltiplos ePSXe abertos e sem PID conhecido, o programa interrompe a leitura para não usar dados do emulador errado. A mão fica vazia ao perder a conexão.

## Fusões
A lista é deliberadamente limitada a **fusões diretas de duas cartas na mão**. Ainda não inclui combinações com cartas da mesa (RAM do campo não validada) ou cadeias de três a cinco cartas. A ordenação por ATK não representa probabilidade, e o fato de a receita ter sido extraída de sete bancos idênticos não comprova todas as condições de uso em duelo.

## Limites atuais
O leitor Windows foi implementado a partir do endereço usado no assistente clássico, mas a nova Alpha ainda precisa ser testada com **ePSXe e ISOs reais**. Ambientes com mapa de RAM diferente podem exigir adaptação de endereços. Os testes automatizados simulam a leitura de RAM e o conteúdo das mãos; imagens de prévia do GitHub usam dados explicitamente sintéticos.

A correção não depende do Ollama nem reanalisa as ISOs a cada tick. Nenhum Memory Card ou save é tocado.
