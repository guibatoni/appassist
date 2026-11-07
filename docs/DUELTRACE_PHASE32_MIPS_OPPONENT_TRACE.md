# DUELTRACE — Etapa 32A: evidência dinâmica MIPS do campo de adversário

**Data:** 2026-11-07 · **Base:** Etapa 31, PR #79 (rascunho)
**Branch:** `feature/dueltrace-v097-runtime-mips-opponent-trace-v32`

## Motivação observável

Auditorias estruturais:
- Galaxy Of Gods NT 2025: 722 cartas, 39 oponentes, 117 matrizes de drops,
  18.553 receitas de fusões, uma janela física; 1.070 padrões MIPS candidatos.
  Fonte: JSON integral fornecido no chat; não houve upload automático deste relatório.
- Rising Of Wicked Gods 1.3.5: 722/39/117, 5.555 receitas,
  três pares conflitantes e uma janela física em `0x2421800`.
  Fonte: relatório privado `reports/iso-forensics/06b3a87fe7c2.json`.
- Enhance Edition Final4: 722/39/117, 24.953 receitas,
  duas janelas possíveis para os 39 adversários, sem promoção de mapeamento.
  Fonte: relatório privado `reports/iso-forensics/6a1a897db35c.json`.

Última sessão Live Diagnostics examinada no repositório de evidências:
251 eventos com ID de adversário candidato 5, cinco cartas de mão coerentes,
15 pares distintos de campos de LP legados, nenhum snapshot de RANK.
O byte estável NÃO comprova ID real do adversário. O registro legado do RANK
não pode ser ativado a partir da mera constância desse byte.

## Implementação Etapa 32A

- `scanner/dueltrace_opponent_mips_trace.py`: lê **somente** arquivo
  `.log`/`.txt` de depurador fornecido pelo usuário. Procura registros
  explícitos `PC=0x...`, `OP=LB|LBU|SB`, `ADDR=0x...`, `VALUE=0x...`.
  Campo clássico `0x8009B361` é uma **pista da versão original**, não
  universal. Endereços alternativos só entram no relatório investigativo
  com >=3 leituras, >=1 escrita e >=2 PCs. 
- Limites: 8 MiB; até 250 mil linhas, 50 mil eventos de bytes,
  4.096 endereços distintos, seis candidatos mostrados. Formatos fora
  dos limites abortam com status explícito. Não armazena texto bruto,
  ROM, nomes, receitas, caminhos, tokens ou dados de memória além dos
  valores 0-39 já expostos como **observações não verificadas**.
- `DueltraceWebBridge.import_rank_trace` agora registra, junto à evidência
  MIPS de RANK, `opponentFieldEvidence`. Os relatórios são locais,
  ligados à ISO ativa cadastrada, salvos na área de traces existente.
  **Não** modifica perfis de mod ou habilita drops, RANK ou fusões.
- Na tela Live Diagnostics, botão
  **Importar trace MIPS (.log/.txt)** mostra contagens de acesso ao campo
  clássico, outros endereços candidatos e leituras das tabelas RANK,
  quando existentes. A interface alerta que o log não prova execução
  autenticada do jogo, identidade do oponente nem causalidade.
- Se dez ou mais eventos contiverem ID candidato, mas nenhum RANK, a
  interface explica que o Live Diagnostics consome snapshots recentes
  do painel de RANK e **não** inicia calibração automaticamente.
- Testes unitários com logs sintéticos + regressão de importação no
  bridge. Testes/CI não comprovam uso em ePSXe real.

## Como realizar um teste útil no Windows

1. Instale a Preview desta branch em **pasta separada**.
2. Abra uma ISO cadastrada, mantenha Live Diagnostics ativado quando
   estiver jogando. Qualquer envio periódico permanece opcional e
   separado da importação de trace.
3. **Se houver um depurador compatível** que exporte log MIPS de um
   duelo, com PC/OP/ADDR/VALUE, clique em "Importar trace MIPS".
   Sem esse log, o botão não cria PC execution trace por conta própria.
4. Conferir no aplicativo se houve acesso a `0x8009B361` e se outros
   bytes com leitura/escrita são candidatos. Registre os resultados
   por ISO, **não** infira que o endereço clássico é válido para todos.
5. Para provar associação adversário→bloco de drops, ainda precisamos
   rastrear leitura real de índice/ponteiro de blocos na execução,
   comparar duelos em adversários diferentes e observar recompensa/RANK
   de um mesmo duelo. Trace somente com PCs não prova esse vínculo.

## Limitações que permanecem abertas

- **RANK MIPS real:** cobertura do logger e instruções que leem os
  critérios ainda não estão autenticadas no ePSXe. Candidatos heurísticos
  estáticos (994–1.070) são pistas, não funções corretas identificadas.
- **Enhance:** 40 blocos estruturalmente plausíveis, 2 janelas de 39.
  Não escolher offset por soma 2048.
- **Rising:** três pares de fusões contraditórias permanecem em quarentena.
- **Galaxy:** a função compatível em jogo declarada pelo usuário
  não altera as flags `verifiedInGame=false` do laboratório estático.

## Segurança, continuidade e proteção

- Código de desenvolvimento somente em branch separada, pull request em
  rascunho, sem alterações na `main` nem na instalação do usuário.
- Em nenhuma hipótese importar bytes de ROM, dump de RAM ou texto bruto
  do trace para o repositório privado de evidências automaticamente.
- Nenhuma flag de `mayActivateDrops`, `rankRoutineConfirmed` ou de
  correspondência de adversário pode ser promovida por essa sondagem.
- Próxima etapa: coleta dinâmica mais autônoma dos eventos de escrita/
  leitura do emulador (se suportada com segurança), associação causal
  dos índices de oponentes e diferenciação das duas janelas da Enhance.
