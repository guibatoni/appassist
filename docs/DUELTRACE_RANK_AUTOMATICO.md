# DUELTRACE — RANK ao vivo automático (Preview)

## Objetivo
Abrir o DUELTRACE, selecionar a ISO e jogar no ePSXe, sem digitar LP nem
clicar em "Confirmar LP" a cada duelo. O motor usa **exatamente a fórmula
SPOILS existente** e continua diferenciando o X15 por SHA e os RANKs clássicos.

## Fluxo técnico
- A tela chama `get_rank_auto()` periodicamente. A operação passa pela API
  local autenticada `ProtectedDesktopApi` e pela bridge Python.
- O motor de leitura continua fazendo duas leituras idênticas da estrutura
  candidata em cada chamada ao ePSXe. A ponte aguarda duas consultas
  consecutivas com **mesmo SHA selecionado, PID e LP válido** (duelo iniciado).
- A segunda consulta chama `confirm_rank_lp`, que relê RAM para evitar usar
  LP mudados durante a conferência. Não é necessário clique ou digitação.
- Assim que liberado, o placar muda conforme turnos, magias, ataques, fusões,
  equipamentos e demais critérios do motor existente; mudanças de PID, duelo,
  ISO, LP ou falhas de leitura exigem nova conferência antes de mostrar pontos.
- A projeção continua **provisória**, não é o resultado oficial e não confirma
  que a ISO no ePSXe é a mesma selecionada na interface. O bônus de deck-out
  continua restrito ao marcador X15 já reconhecido.
- Para mod **sem mapeamento RAM validado**, a leitura antiga exige a ativação
  explícita do modo experimental. Feito isso, a conferência de LP é automática,
  mas dois eventos de RAM coerentes continuam necessários antes de calcular.
  A observação experimental não desbloqueia mapeamentos nem confirma drops.
- O caminho anterior `get_rank()` e `confirm_rank_lp` permanece na ponte para
  compatibilidade de diagnósticos/testes, mas não é exigido pela interface.

## Validação
Testes com RAM sintética verificam atualização dos pontos, consistência por
SHA/PID, troca de LP, novo duelo, interrupções, isolamento de mods não
validados e permissão via token. A fórmula de pontos não foi alterada.
O comportamento no computador real ePSXe ainda precisa ser comparado ao
resultado mostrado no jogo, mesmo quando a estimativa acompanha as ações.

## Atualizador
O pacote continua sendo gerado pelo workflow Windows e poderá ser instalado
pelo atualizador in-place da versão anterior após passar na CI; os arquivos
locais do usuário não são modificados pelo cálculo.
