# DUELTRACE v0.9.7 — Limites e evidências dos nomes

## O que esta entrega corrige

A v0.9.6 limitava a leitura a um número fixo de bytes. Se o próximo
ponteiro estivesse fora de ordem ou a mais de 128 bytes, a inspeção
abandonava esse limite e podia consumir bytes de outro registro. O decoder
conhecido também aceitava nomes sem exigir que o `FF` pertencesse ao mesmo
registro. Nomes plausíveis concatenados podiam passar na contagem mínima.

O leitor compartilhado em `scanner/dueltrace_name_boundaries.py` agora:

- Interpreta cada byte como índice da tabela de glifos. Só o valor de cada
  entrada é decodificado por Shift-JIS; o payload não é Shift-JIS direto.
- Usa o próximo início físico conhecido como limite, mesmo com ponteiros
  fora de ordem ou compartilhados. A leitura permanece limitada a 128
  bytes no diagnóstico e 150 no decoder conhecido.
- Registra a presença do cabeçalho `F8 0A` e seu terceiro byte, sem assumir
  que esse byte seja parte do nome.
- Exige `FF` antes do limite e sem glifo ilegível para aceitar uma string
  no decoder tradicional. Não interpreta `FE` ou outro código como novo
  terminador; isso exige um adaptador com evidências próprias.
- Preserva o último glifo legível, inclusive `v`, e seu byte de índice.
  Não remove letras por frequência, nome esperado ou hipótese de IA.
- Audita os 39 ponteiros: posições fora do arquivo, registros que
  compartilham ponteiro e pares consecutivos que não são crescentes.
  Essas ocorrências são diagnóstico, não prova de que aliases sejam
  nomes iguais ou de que a ordem do arquivo deva ser crescente.

`opponent_name_boundaries.records` no relatório local conserva os 39
registros, incluindo o último, com estado explícito da decodificação.
O payload da interface continua contendo somente sete amostras limitadas;
não copia todo o bloco de texto nem o executável.

## Como interpretar as novas evidências

`boundedRecords` conta segmentos cujo próximo início físico foi realmente
alcançado dentro do orçamento. `hasFFBeforeNext` e `noFFBeforeNext` só
contam esses segmentos completos. Quando o limite está além do orçamento,
o resultado da amostra é `null`: não se afirma que faltou `FF` em bytes
que não foram inspecionados.

`terminatedRecords` conta registros que chegaram a `FF` sem encontrar
antes um código inválido, incluindo o 39º quando possível. Um `FF` após
um código inválido pode aparecer em `hasFFBeforeNext`, mas não transforma
o prefixo em nome decodificado. `terminatorOffset` é relativo ao payload,
depois do cabeçalho quando presente. `lastGlyphHex` é o índice de byte,
não o próprio valor Shift-JIS da entrada da fonte.

Há uma limitação deliberada: tabelas com *suffix interning* podem ter um
ponteiro no início de um nome e outro no meio dele, compartilhando o mesmo
`FF`. Sem evidência de que esse layout utiliza esse recurso, a string
externa recebe `ambiguousBoundary: true` e fica pendente; o decoder não
atribui automaticamente o terminador da string interna à externa. Isso
não prova corrupção nem exige remover texto. Um adaptador comprovado
poderá reconhecer esse formato separadamente. Aliases com o mesmo
ponteiro exato continuam decodificáveis, sem comprovar equivalência de IDs.

Estados distinguem término reconhecido, glifo inválido, falta de `FF`
antes do próximo registro, orçamento esgotado, fim do arquivo, cabeçalho
incompleto e ponteiro fora do arquivo. Mesmo um nome decodificado não
comprova sua identidade no jogo: `validated` permanece `false` em todo
o diagnóstico.

## Testes e preservação

Fixtures inteiramente sintéticas cobrem 722 cartas/39 oponentes com `FF`,
atributos preservados, cabeçalho tradicional, sufixo `v` legítimo,
terminador alternativo não reconhecido, `FF` emprestado do próximo nome,
ponteiros fora de ordem/compartilhados/fora do arquivo, orçamento de
leitura e arquivo/cabeçalho truncados. O sanitizer mantém sete amostras,
limita contagens e não transforma flags de um relatório em validação.

Nenhuma fórmula de RANK/Spoils, regra de SHA do X15 ou receita de fusão
foi alterada por esta correção de nomes.

## Validação real do GOG MOD ainda pendente

As amostras legíveis relatadas na v0.9.6 não determinam o significado do
`v`. Não houve acesso ao `GOG_VNT.223`, à ISO ou a um duelo real nesta
entrega. Portanto não há afirmação de recuperação dos 39 nomes, de
validação das 722 cartas ou de associação dos 4.543 drops provisórios.

Para fechar essa etapa com a ISO fornecida localmente pelo usuário:

1. Reanalisar o perfil específico pelo SHA-256 para gerar as novas
   evidências; relatórios antigos não ganham esses campos retroativamente.
2. Comparar os 39 registros locais ao jogo e revisar cabeçalhos, índices
   de glifos, próximo limite físico e estado de cada string. Nenhum nome
   pode ser aprovado só porque perdeu um sufixo ou parece familiar.
3. Se houver um novo código de controle, demonstrar sua função com
   limites e registros independentes, acrescentar fixtures sem recursos
   do jogo e criar um adaptador isolado por evidência de layout/SHA.
4. Validar separadamente IDs e atributos das 722 cartas antes de liberar
   a associação dos pesos provisórios a cartas/oponentes e probabilidades.

Não se distribuem imagens de jogo, executáveis PS1 ou tabelas comerciais
nos testes nem no repositório.
