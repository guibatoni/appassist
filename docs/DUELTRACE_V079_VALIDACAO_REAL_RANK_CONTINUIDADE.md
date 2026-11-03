# DUELTRACE v0.7.9 — RANK: prova de leitura WA, hipóteses de drops e diagnóstico offline

**Branch de trabalho:** `feature/dueltrace-v079-rank-proof-pipeline`  
**Base:** `feature/dueltrace-v078-rank-drops-filters-evidence` (PR #28).  
**Sistema-alvo:** Windows + ePSXe, sem alteração de memória do emulador.

## Motivação e escopo

O objetivo é sair de uma tabela WA reconhecida *estaticamente* para uma
correlação reproduzível de resultados dos duelos com:
1. qual banco de drops pertence a cada grupo de RANK;
2. quais pares limiar/pontos de RANK foram efetivamente lidos por
   instruções MIPS no emulador;
3. qual foi a pontuação real observada ao fim do duelo.

**Nenhuma dessas evidências, isoladamente, demonstra a causalidade do
RANK final.** Nem o nome do mod nem o hash de uma tabela bastam.

## Entrega implementada

### Resolução de drops sem forçar nomes

`scanner/dueltrace_rank_drop_solver.py` enumera as seis permutações
possíveis entre os três bancos WA e os rótulos Z-POW, S-POW e S-TEC.
Para cada duelo registrado, elimina apenas bancos que não contêm a carta
recebida pelo jogador naquele oponente. Se não houver associação
bijetiva, sinaliza contradição em vez de atribuir correspondência falsa.
Um banco é sugerido para um RANK somente quando todas as soluções
compatíveis concordam e há ao menos dois duelos de dois oponentes
distintos. Mesmo assim a saída é `corroborado_manualmente`.

A interface agora informa quantas hipóteses são ainda possíveis.

### Inspeção de leitura de tabela WA na execução MIPS

`scanner/dueltrace_rank_memory_trace.py` interpreta logs de um
**depurador instrumentado** que contenham campos exatos:
```text
PC=0x80012040 PHASE=RANK OP=LHU ADDR=0x80030000 VALUE=0x0005
PC=0x80012044 PHASE=RANK OP=LH ADDR=0x80030002 VALUE=0x000C
```
Esses exemplos são **sintéticos**, não endereços observados na ISO do usuário.

Quando há ao menos quatro pares distintos entre uma leitura `LHU` de
limiar e uma leitura `LH` dos pontos assinados em endereços adjacentes,
cujos valores correspondam aos mesmos pares da tabela RANK extraída do
WA da ISO ativa, numa janela de candidato do SLUS, o DUELTRACE marca
`tableReadsObserved: true` — **não**
`rankRoutineConfirmed`. Também recusa log com phase incorreta,
endereço impossível, valores divergentes e excesso de registros.

O ePSXe não deve ser presumido como capaz de produzir esse formato
automaticamente sem um depurador/logger compatível. A função importa
um log já exportado; **não** injetar hooks, instalar software de
proveniência duvidosa nem desativar antivírus para obter o log.

### Relatório de investigação por ISO

`scanner/dueltrace_rank_export.py` constrói JSON portátil com SHA da ISO,
SLUS e WA, estrutura numérica das tabelas, hipóteses restantes de
drops, resultados de duelos informados, comparação de pontos,
endereços MIPS candidatos e evidência resumida dos traces.

Botão na aba Drops: **Exportar relatório RANK da ISO**. O Windows
permite escolher o destino. O arquivo não contém ROM, executável,
artes, dados brutos RAM, logs integrais, caminhos do computador nem
tokens. Não substitui arquivos existentes; seleção com mesmo nome
deve ser refeita. Hash do relatório valida integridade dos dados do
JSON, não a autenticidade da observação manual.

## Como executar a validação com ISOs reais

Para cada ISO (Remaster X15, FM13 Drop x15 e FM Original Drop x15):

1. Importar a imagem local em **Mods** (somente cópia própria legal).
2. Abrir **Drops** e verificar quais bancos o scanner encontrou.
3. Vencer oponentes diferentes, registrar o oponente, RANK mostrado,
   tipo de vitória, ID da carta recebida e pontos na tela.
4. Caso possua logger MIPS compatível, exportar seu registro *durante
   o duelo*, importar o `.log` ou `.txt` e observar leituras de tabela.
5. Clicar **Exportar relatório RANK da ISO**, salvar o `.json` e
   compartilhar apenas esse relatório para auditoria.
6. Repetir em cada mod e comparar SHAs, pesos e contradições. Não
   transformar observação manual em resultado confirmado automaticamente.

**Não foi executada uma partida real de ePSXe neste ambiente.**
A confirmação causal da rotina de pontuação, inclusive os endereços
definitivos de memória e classificações de todos os mods, permanece
pendente de traces e resultados coletados no computador do jogador.

## Segurança

- O código do DUELTRACE só abre localmente o arquivo que o usuário
  escolhe; não transmite ISO, binários nem dados sensíveis.
- Compatibilidade por SHA do mod, sem herdar tabela ou RAM de outro mod.
- Trace .log/.txt limitado a 8 MiB e a número máximo de eventos.
- Relatório JSON é criado apenas no destino escolhido, sem sobrescrita.
- Pacotes Windows Preview NÃO assinados ainda não podem ser considerados
  releases comerciais nem atualizados automaticamente ignorando o Defender.
- Não commitar ROMs nem arquivos SLUS/WA extraídos ao GitHub.

## Estado de validação

Conferir o último HEAD e CI da branch antes de declarar sucesso.
Os testes automatizados usam apenas dados sintéticos, não ROMs reais.

## Prompt de continuidade completo

> Continuar o DUELTRACE para Windows no repositório
> https://github.com/guibatoni/appassist, branch
> `feature/dueltrace-v079-rank-proof-pipeline`, baseada em
> `feature/dueltrace-v078-rank-drops-filters-evidence` PR #28.
> A v0.7.9 implementou um resolvedor exaustivo das seis possíveis
> associações banco de drops WA ↔ Z-POW/S-POW/S-TEC, com detecção de
> ambiguidades e contradições, sem atribuição arbitrária.
> Acrescentou auditor de execução MIPS que compara eventos PC, LHU,
> LH, endereços e valores lidos com ao menos quatro pares de
> limiar/pontos da tabela RANK extraída da própria ISO, marcando
> `tableReadsObserved` sem declarar `rankRoutineConfirmed`.
> Criou exportação local de JSON de evidências por SHA, sem ROM,
> SLUS, WA, caminhos locais, RAM bruta ou logs integrais, disponível
> na aba Drops. Reunir relatórios e traces dos mods X15, FM13 e
> Original, testar no Windows com duelos reais e validar acesso à
> tabela, sequência de pontuação e score final. Somente após
> validação independente criar bindings automáticos para cada SHA.
> Preservar todas as funcionalidades anteriores, filtros, segurança,
> atualizador assinado e PRs de base. Conferir HEAD e CI do PR da
> v0.7.9; não afirmar execução de qualquer mod com base em testes
> sintéticos. Ao encerrar, registrar novo prompt com versionamento,
> testes, limitações e pendências.
