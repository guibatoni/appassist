# DUELTRACE — Backup de continuidade Etapa 26 (06/11/2026)

## Fonte e preservação

- Repositório: https://github.com/guibatoni/appassist
- Etapa 25: PR #73, branch `feature/dueltrace-v097-live-diagnostics-v25`, commit de código testado `089d6773e3d7be92afbd7b6442b814f2d8b611a7`; CI histórica 754 testes + Windows, Preview `preview-v0.9.7-r42283346075`.
- Backup anterior: `docs/BACKUP_CONTINUIDADE_ETAPA25_2026-11-06.md`.
- Etapa 26: branch `feature/dueltrace-v097-live-probe-evidence-v26`, derivada do HEAD documental da Etapa 25 `fdaec9dc4ab2dcf002d92a2dd85fbe8bea336107`. Não mesclada à main; **CI e preview da Etapa 26 ainda não validados**.
- Biblioteca de 722 cartas, leitura da mão (5 cartas) e artes: funcionamento informado e protegido. Nenhum arquivo de Biblioteca de cartas ou artes modificado nesta etapa.

## Descoberta no código

A contagem `validatedHandAnchors` era incrementada somente no final de `_valid_psx_sample`, após as verificações dos campos legados de adversário e LP. Quando a mão coincidia mas os offsets legados falhavam, o diagnóstico ocultava o sucesso da âncora. Isso era uma deficiência de observabilidade; **não prova** o layout da RAM do GOG.

## Implementação nova

1. `scanner/dueltrace_live_opponent.py`: registra a âncora da mão assim que validada; para a tentativa do endereço inferido pela mão, reporta um sinal booleano e contadores por estágio sem bytes nem endereços.
2. `scanner/dueltrace_live_diagnostics.py`: exporta os novos sinais usando allowlist estrita e números, sem abandonar a etiqueta provisória; `mayActivateDrops=false`, `mayActivateRank=false`.
3. `tests/test_dueltrace_live_opponent.py` e `tests/test_dueltrace_live_diagnostics.py`: novos casos sintéticos de rejeição e sanitização.
4. Documento técnico: `docs/DUELTRACE_PHASE26_HAND_ANCHOR_EVIDENCE.md`.

## Estado de evidências

**Confirmado no código prévio:** 39 nomes estruturais (posições, não IDs); 40 blocos, 160 matrizes candidatas, Biblioteca 722/722, leitor de mão existente. **Ainda não confirmado:** ID real do adversário, mapeamento ID→bloco, matriz→RANK, drops, rotina MIPS, fusões para todo mod.

**Etapa 26 ainda depende:** CI da branch, build Windows e primeiro JSON gerado com a versão nova em duelo real ePSXe. Os novos testes são sintéticos; não declará-los aprovados antes do CI.

## Próxima ação

Quando houver build validado, o jogador deve abrir GOG no ePSXe, ativar o mod no DUELTRACE, executar um diagnóstico por uma sessão normal, parar e colar o JSON. Priorizar os campos `knownHandAnchorAtHint`, `hintRejectionCounts`, `hand.ready`, `opponent.status`, `rejectionCounts`. Não exigir registros manuais repetidos, não liberar drops por hipótese e não conectar telemetria remota sem autorização.

## Continuidade Biblioteca ChatGPT

Destino pretendido: `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/`. Documentos antigos Etapa 15 ficam históricos. Este backup deve ser guardado como novo arquivo, nunca substituindo evidências antigas ou snapshots. As observações reais só passam a confirmadas depois de análise do relatório e inspeção do executável.

## Comportamento de segurança

Não transmitir ROM, caminhos, endereços RAM, tokens ou arte; somente leitura do ePSXe. Não fazer merge na main sem autorização. Salvar backup ao encerrar cada etapa.
