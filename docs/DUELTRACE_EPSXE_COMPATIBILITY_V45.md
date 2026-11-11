# DUELTRACE — Etapa 45 · Compatibilidade de versões ePSXe (Windows)

## Problema identificado

A versão anterior lia a mão pelo endereço físico **fixo do processo**
`0xBFF484`, que corresponde ao deslocamento emulado `0xEA484` a partir
da base host `0xB15000`. Isso funciona em certas instalações, mas endereços
de memória do Windows variam por executável, versão, layout de carregamento e
ASLR. Encontrar o processo `ePSXe.exe` sozinho NÃO garante uma mão válida.

Os executáveis históricos e atuais do ePSXe possuem versões diferentes
(v1.0.x, 1.2, 1.5.x, 1.6, 1.7, 1.8, 1.9.x, 2.0.x; **v2.0.18** foi publicada
para Windows em 23/12/2025: https://www.epsxe.com/).

## Alterações deste build

1. **Detecção de processo:** reconhece `ePSXe.exe` e cópias com sufixo de
   versão (por exemplo `ePSXe 2.0.18.exe`, `ePSXe-2.0.5.exe`). O nome deve
   corresponder estritamente a ePSXe, não a outro emulador ou nome arbitrário.
2. **Leitura antiga preservada:** testa primeiro `0xBFF484`; se a mão tiver
   cinco IDs válidos e indices dos slots corretos em duas leituras, mantém o
   comportamento anterior sem varredura.
3. **Localização de RAM:** se o endereço antigo falhar, procura regiões de
   memória virtual **pertencentes somente ao processo ePSXe selecionado** por
   `VirtualQueryEx`, verificando sua proteção e commit; nenhuma escrita.
4. **Estrutura PS1:** encontra a assinatura de mão (5 × 28 bytes; IDs de
   1–722; indices dos slots de 0–4), até **48 MiB** de leituras de memória.
   Não exige que a base esteja alinhada em 64 KiB. Regiões altas de Windows
   64-bit também são consideradas.
5. **Verificação:** lê cada candidato duas vezes e só aceita um candidato
   estável. Se houver duplicidade, memória parcialmente carregada ou nenhuma
   estrutura válida, retorna **indisponível**, nunca cartas inventadas.
6. **Cache temporário por PID**, revalidado a cada consulta. Enquanto o
   usuário não está em duelo, evita repetir varreduras completas em toda
   atualização de interface (intervalo mínimo de 7 s entre tentativas falhas).
7. **Leitor de oponente:** reutiliza uma mão dinâmica validada como âncora
   independente; IDs e LP continuam provisórios, sem promover nomes, drops
   ou identidade da ROM.
8. **Projeção X15 experimental:** transfere apenas o endereço candidato
   do registro RANK quando a mão do **mesmo PID** foi validada em outra
   base. Não altera fórmulas, faixas ou bindings de outros mods.

## Limites honestos

- O scanner usa estrutura de memória observável **durante um duelo de
  Yu-Gi-Oh! Forbidden Memories**. Não é uma prova de compatibilidade
  com cada versão, nem garante detectar a RAM enquanto está em um menu.
- **Detectar ePSXe ≠ identificar a ISO no drive do emulador.** Nomes de
  cartas continuam ligados à ISO ativada manualmente no DUELTRACE.
- Endereços de RANK, eventos de duelo e dados de oponentes podem ser
  específicos de cada mod. A atualização não declara que todos esses
  recursos funcionam em todas as versões sem validação independente.
- Não acessa BIOS, Memory Cards, saves, rede ou ROM para localizar a RAM.
  Não modifica nem injeta código no emulador.
- A integração automática para *iniciar* uma ISO no ePSXe continua usando
  a linha de comando anterior. Em versões muito antigas, caso o emulador
  ignore opções, abra o jogo manualmente no ePSXe; a leitura ainda pode
  se conectar ao processo. Não alterar parâmetros nem presumir que todos
  os executáveis aceitam `-loadiso`.
- A edição é **somente Windows**. A versão Android/Linux/Mac do ePSXe
  não é abrangida.

## Plano de confirmação real

Use uma ISO selecionada no DUELTRACE e o ePSXe aberto **durante o duelo**.
Compare as cinco cartas com a tela do jogo e anote a versão exata. Repita
com pelo menos duas partidas, inclusive após reiniciar o ePSXe, para
verificar que os ponteiros não são reutilizados incorretamente.

Matriz de versões para QA manual: 1.5.2, 1.6.0, 1.7.0, 1.8.0,
1.9.0, 1.9.25, 2.0.0, 2.0.2, 2.0.5, 2.0.18. Nenhuma foi marcada como
**confirmada na máquina do usuário** apenas pelos testes unitários:
estes exercitam layouts sintéticos variados em Win32/Win64.

Se uma versão não produzir mão válida: informar a versão do ePSXe,
indicar se o jogo está em duelo e fornecer somente o status mostrado
pelo DUELTRACE. Não solicite credenciais nem despejos completos de RAM.

## Correção v46 — varredura que não prosseguia

Uma imagem real da interface demonstrou o ePSXe já em duelo com cinco cartas, enquanto a Central de Duelo não conseguia identificar a RAM. O scanner anterior tinha orçamento de leitura de 48 MiB por tentativa, mas **reiniciava sempre do começo** na tentativa seguinte. Se a mão estava em uma região posterior, jamais seria localizada.

A versão v46 passa a salvar **apenas em RAM, por PID**, a posição de leitura e a assinatura da lista de regiões. A próxima leitura retoma desse ponto se a disposição das regiões não mudou; se mudou, reinicia com segurança. O limite de 48 MiB **por tentativa** continua, evitando travamentos, mas a cobertura progride entre as tentativas. Testes sintéticos incluem uma mão em posição posterior ao primeiro bloco e conferem que o estado do scanner é descartado quando a mão é validada.

Também há sondas iniciais limitadas no deslocamento de mão PS1 para detectar rapidamente layouts simples, mantendo a validação por duas leituras. A mensagem de espera distingue ePSXe detectado de estrutura de mão ainda não validada. Não houve mudança de endereços de ISO, fórmulas de RANK ou permissões de escrita. Somente partidas reais nas versões específicas do usuário confirmam o funcionamento final.
