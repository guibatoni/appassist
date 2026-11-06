# DUELTRACE — Etapa 14: validação binária real do GOG MOD 2.2 (ISO fornecida)

## Fonte e cuidados

O usuário forneceu localmente a imagem `GOG MOD 2.2 - Drop 15 (NDC).iso`.
Esta etapa analisou o conteúdo **somente na sessão de trabalho**; nenhum
setor, executável, arte, lista de personagens ou ROM foi enviado ao GitHub.
Os testes automatizados geram seus próprios dados sintéticos.

O arquivo é um disco PS1 RAW de setores de 2352 bytes, Mode2 Form1,
com diretório ISO9660 válido. O `SYSTEM.CNF` aponta para o executável
`GOG_VNT.223` (não SLUS/SLPS). O scanner já identifica esses
nomes de inicialização, preservando a seleção baseada em conteúdo.

## Descoberta 1: cabeçalho PS-X EXE e truncamento aparente

- `GOG_VNT.223`: tamanho registrado no diretório: **1.902.032 bytes**.
- Cabeçalho PS-X EXE: 2.048 bytes, payload declarado: **1.900.544 bytes**.
- Payload disponível *somente pelo tamanho ISO9660*: **1.899.984 bytes**.
- Diferença: **560 bytes**.
- A extensão física de 929 setores de 2048 bytes comporta exatamente
  **1.902.592 bytes** (cabeçalho + payload declarado).
- Os 560 bytes além do tamanho do diretório **existem fisicamente
  e são todos zero**. O setor não se sobrepõe a nenhum outro arquivo.
- Com o comprimento completo do último setor, os campos
  de carga RAM, ponto de entrada, tamanho e assinatura do PS-X EXE
  são coerentes.

Correção genérica: `dueltrace_exe_sector_padding.py`. Só estende o
executável quando o cabeçalho exige até 2047 bytes adicionais dentro
do setor **já alocado**, esses bytes são zeros efetivamente lidos e
não há sobreposição de extents; a validação PS-X EXE completa deve
passar. Não acrescenta zeros inventados nem ignora cabeçalhos inválidos.

## Descoberta 2: os 39 nomes estão no próprio executável

Os índices de ponteiros 809–847 (0x329–0x34F) contêm
**39 ponteiros distintos e 39 prefixos de texto distintos**. Entre eles
estão nomes de adversários reconhecíveis. Todos os registros seguem:

```text
[3..60 glifos codificados] FD [u16 little-endian] FF
```

Para **todos os 39** registros observados:

```text
field_u16 - quantidade_de_glifos_codificados = 0x19A8
```

A constante 0x19A8 foi **inferida dos próprios registros do GOG**,
não é usada como valor hardcoded pelo novo scanner. O campo FD
pode representar formatação/posição; não assumir que é uma referência
de texto na ISO nem alterar a rotina MIPS sem prova.

A revisão anterior tratava FD como potencial fim ou salto, e descartava
nomes quando encontrava bytes não nulos depois dele.

O novo `dueltrace_inline_fd_names.py` encontra uma janela **única**
de 39 nomes somente se todos exibirem exatamente `FD u16 FF`,
os valores de campo tiverem a mesma relação afim com os comprimentos
codificados, todos os ponteiros/nomes forem diferentes e a tabela de
glifos for válida. Se duas janelas satisfizerem os critérios, rejeita
ambas como ambíguas. A descoberta pode alimentar o catálogo de
adversários **estrutural**, com `inGameVerified=false`, nunca
ranks, drops ou fusões automáticos.

## Descoberta 3: contêiner de pesos compatível com formato clássico

O arquivo `G0SD/GOG_SD1.23` tem **38.148.608 bytes**, o mesmo
tamanho de contêiner conhecido. Nos offsets clássicos de 39 decks e
3 tabelas de drops por adversário, foram observadas:
- **39** matrizes candidatas de deck;
- **117** matrizes candidatas de drops (39 × 3);
- 722 inteiros u16 por matriz, cada uma com soma **2048** e sem
  nenhum peso superior a 2048.

É forte evidência de correspondência **estrutural** com os bancos
de probabilidade do jogo, mas ainda não prova associação entre os
índices de adversários e os grupos, nem quais rótulos de rank
(S-POW, TEC etc.) pertencem a esta ISO. Não desbloquear as tabelas
sem confirmação independente em jogo.

## Implementado — parser revisão 28

1. Leitura do último setor PS-X EXE, somente para padding zero
   comprovado e contido no extent do arquivo.
2. Identificação de `FD u16 FF` por relação uniforme com comprimento
   do nome, sem codificar o nome do mod, nomes de adversários ou offsets
   específicos de um exemplar.
3. Publicação limitada dos **39 nomes estruturais**, mantendo
   `inGameVerified=false`, `rankVerified=false` e
   `dropsVerified=false`.
4. A revisão 28 invalida o cache anterior. O relatório compacto
   não revela os nomes nem bytes, mas apresenta
   `inlineFdEvidence`.

## Verificação

Testes de fixture sintética cobrem:
- 39 nomes distintos, esquema FD u16 FF e base derivada;
- rejeição de metadados inconsistentes;
- rejeição de duas janelas igualmente plausíveis;
- padding zero de último setor aceito;
- padding não nulo, cabeçalho incoerente e extents sobrepostos rejeitados;
- preservação dos 722 nomes de cartas e isolamento de drops/rank.

### Próximos passos

1. Testar Preview do parser 28 com **Atualizar dados** no GOG real.
2. Confirmar contagem de 39 adversários com aviso estrutural.
3. Comparar em duelos os índices e nomes observados com a ordem
   candidata extraída, antes de ativar drops e a associação ao rank.
4. Investigar os grupos das 117 tabelas e rotinas MIPS da mesma ISO,
   com comparação por adversário/resultado real.
5. Repetir provas com outros mods para detectar diferenças no
   formato de nomes, tamanhos do EXE e bancos de drops.

A ISO real não deve ser adicionada ao repositório nem ao pacote
de continuidade, e as mudanças ficam numa PR de revisão.
