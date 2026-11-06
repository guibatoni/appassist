# DUELTRACE — BACKUP DE CONTINUIDADE E CONGELAMENTO DA ETAPA 25

**Data:** 06/11/2026. **Fonte:** resumo de desenvolvimento e evidências fornecidas pelo usuário + GitHub PR #73/CI/release verificados. **Destinação desejada na Biblioteca:** `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/`.

> IMPORTANTE: Este arquivo é a referência de continuidade mais recente. Os documentos antigos em `PROJETO_ATUAL`, especialmente `00_LEIA_PRIMEIRO.md` e `04_ROADMAP_E_CRITERIOS.md`, estavam atualizados só até a Etapa 15 na inspeção desta sessão. Eles são históricos, não o estado vigente. Não substituí-los silenciosamente.

## 1. Fontes canônicas e versão verificável

- Repositório: https://github.com/guibatoni/appassist
- PR atual **#73** (draft, aberta, sem merge): https://github.com/guibatoni/appassist/pull/73
- Branch: `feature/dueltrace-v097-live-diagnostics-v25`.
- Commit de código **congelado e testado**: `089d6773e3d7be92afbd7b6442b814f2d8b611a7`. Commits posteriores só de documentação/backup podem tornar o HEAD da branch diferente.
- CI push **aprovada**: https://github.com/guibatoni/appassist/actions/runs/42283346075 — **754 testes Python**, compilação de interface Windows, empacotamento e auditorias aprovados.
- Preview Windows **publicada**: https://github.com/guibatoni/appassist/releases/tag/preview-v0.9.7-r42283346075
- ZIP instalável: https://github.com/guibatoni/appassist/releases/download/preview-v0.9.7-r42283346075/DUELTRACE-WebUI-Windows-Preview.zip
- SHA256 do ZIP instalável: `096ed9075808ae26a05c85e94c88eddce3e9819055bb73a458eb02ec8e1d1fb9` (informado pela publicação oficial; verificar hash antes de executar).
- Snapshot do CÓDIGO em commit imutável: https://github.com/guibatoni/appassist/tree/089d6773e3d7be92afbd7b6442b814f2d8b611a7
- Link de arquivo de código do GitHub (download gerado pelo GitHub): https://github.com/guibatoni/appassist/archive/089d6773e3d7be92afbd7b6442b814f2d8b611a7.zip
- PRs dependentes ainda em draft e **não mescladas à `main`**: #61 (Etapa14) → #62 (Etapa15) → [...] → #68 (20) → #69 (21) → #70 (22) → #71 (23) → #72 (24) → #73 (25). Começar pelo commit da Preview, não pela `main`, e verificar dependências antes de editar.

## 2. Objetivo do produto

DUELTRACE: assistente Windows, visual moderno PT-BR, para Yu-Gi-Oh! Forbidden Memories e mods `.iso/.bin`. Fluxo final pretendido: usuário abre o aplicativo, seleciona a ISO e joga; cartas/artes/fusões/oponentes/drops/RANK devem vir dos bytes reais da ISO ou da execução do jogo, sem preenchimento manual. Compatibilidade universal é META, não fato comprovado. Proteger dados locais e evitar supor que uma ISO é igual à outra.

## 3. Funcionalidades observadas pelo usuário

- No GOG MOD 2.2 - Drop 15 (NDC).iso, a Biblioteca mostra **722/722 cartas** com nomes, tipos, ATK e DEF coerentes com o jogo (confirmado pelo usuário), inclusive artes visuais obtidas/baixadas e exibidas. Preservar o sistema de cartas e artes: **não reescrever nem regressar**.
- A Central de Duelo mostra 5 cartas na mão em tempo real (capturas reais do usuário, inclusive IDs 449,145,447,629,468) e imagens; é uma leitura de RAM já funcional.
- A interface de RANK mostrou como exemplo **86 pts / A-POW**; isso é saída observada, **não valida o cálculo universal, a rotina MIPS, nem os grupos de drops do GOG**.
- Biblioteca de Mods detecta **39 nomes estruturais de adversários**, mas as posições 1–39 são **índices estruturais**, não IDs internos confirmados em duelo.
- Contêiner de dados do GOG: família detectada de **40 blocos físicos**, stride 0x1800, início estrutural 0xE99800; 1 matriz de deck + 3 de recompensas (722 pesos u16, soma 2048) por bloco, **160 matrizes** e duas possíveis janelas de 39 oponentes. Grupos/ranks não associados.
- Explorador automático de matrizes da Etapa 22 já exibe blocos, cartas com seus nomes/atributos, pesos e estimativa condicional do peso/2048; esses valores **não são drops oficiais**.
- Leitor experimental de ID na RAM do ePSXe estava falhando em duelo real. Uma captura revelou 128 bases candidatas sem identificação; a Etapa 24 introduziu âncora pela mão de cinco cartas e corrigiu leitura de 140 bytes. **Teste real da correção Etapa24/25 ainda pendente**.

## 4. Evidência GOG — manter interpretação conservadora

- `SYSTEM.CNF` aponta `GOG_VNT.223`, executável PS-X EXE com diferença de 560 bytes de padding zero em setor físico; correção de leitura na Etapa14.
- 39 strings reais no formato `[glifos] FD [u16 LE] FF`, relação uniforme `campo - comprimento = 0x19A8`. Nomes estruturais extraídos mas não vinculados a IDs internos.
- Tentativas de evidência manual: houve capturas de Simon Muran B-POW recebendo #449, #449, #450, e outra tela com #62 e índice físico candidato 11. **Não reunir automaticamente registros de sessões diferentes como se fossem o mesmo conjunto ativo**; havia exclusões/reinicializações entre testes. Conservar documentos de evidência da Biblioteca.
- Zero janelas compatíveis sob hipótese 'posição de nome = índice de bloco' **não invalida** as tabelas: só refuta aquela hipótese. Recompensa ausente não deve contar como conflito independente de RANK.
- O explorador já permite consultar os 40 blocos sem assumir a ordem dos adversários; nenhum pool de drops nem rank foi confirmado.

## 5. Linha cronológica recente

| Etapa | PR | Resultado |
|---|---|---|
|14|#61|Leitura direta GOG, nomes FD/u16/FF, padding do executável, matrizes reais|
|15|#62|Detector de família estrutural genérico (40 blocos, duas janelas de 39)|
|16–19|#63–#67|Diagnósticos MultiMod, observações, identificação pelo nome, preservação de hipóteses|
|20|#68|Histórico dos registros de duelo, incompatibilidades por causa, desfazer último registro|
|21|#69|Varredura dos blocos físicos sem fixar IDs; evita duplicar conflito de RANK|
|22|#70|Explorador automático das matrizes + sonda inicial de ID no ePSXe|
|23|#71|Busca RAM ampliada e contadores de rejeição; falhou no PC em duelo real|
|24|#72|Âncora pela mão comprovada, 140 bytes em vez de 48, investigação RAM mais específica|
|25|#73|**Live Diagnostics** local opcional, coleta contínua e exportação sanitizada para ChatGPT; 754 testes e Preview aprovados|

## 6. Etapa25 — Live Diagnostics

Implementada na **Biblioteca de Mods**, separada da Central de Duelo para manter a home limpa:

1. **Iniciar diagnóstico**: opt-in do usuário, inicia amostragem em thread local aproximadamente a cada 3 segundos.
2. Coleta somente saídas de sondas existentes: 5 IDs de cartas lidos, ID e LP candidatos do oponente quando legíveis, estados e motivos de rejeição da RAM e último RANK já observado; **não força calibração de RANK**.
3. **Parar diagnóstico**: encerra sessão, preservando o histórico. Mudanças idênticas são deduplicadas.
4. **Copiar relatório para o ChatGPT**: JSON com allowlist estrita, máximo 360 eventos de mudança, exportação ~140 KB. Arquivo local separado por SHA da ISO e por sessão; não inclui binários, ISO, artes, dumps, caminhos do PC, PID, token nem endereços RAM.
5. **Não há conexão remota automática do ChatGPT ao PC.** Para analisar neste chat, a pessoa deve copiar o relatório e colá-lo, ou disponibilizá-lo explicitamente por meio seguro posteriormente. Não prometer leitura contínua pela conversa sem instalar/autorizar um serviço remoto.
6. Não ativa drops, fusões nem RANK por hipótese. A leitura do byte do adversário ainda não foi comprovada para o GOG.

Arquivos de código recentes: `scanner/dueltrace_live_diagnostics.py`, `scanner/dueltrace_live_opponent.py`, `scanner/dueltrace_web_bridge.py`, `scanner/dueltrace_web_security.py`, `web/lib/desktop.ts`, `web/components/desktop/desktop-page.tsx`, `tests/test_dueltrace_live_diagnostics.py`, `tests/test_dueltrace_web_bridge.py`. Documentação da fase: `docs/DUELTRACE_PHASE25_LIVE_DIAGNOSTICS.md`.

## 7. Próxima ação concreta (nova conversa)

**Primeiro:** confirmar código no commit fixo e CI, abrir a Preview Etapa25 e verificar que a interface apresenta Live Diagnostics na Biblioteca de Mods. Solicitar um **único relatório JSON** após uma sessão normal do GOG, não novos registros manuais de carta/RANK. Se o usuário já colou o relatório, analisá-lo imediatamente. Checar se o monitor captura a mão e as falhas de sonda ao mesmo tempo.

**Depois:** correlacionar sinais da mão que já funciona com byte candidato de adversário na RAM do ePSXe; identificar por inspeção da rotina MIPS do executável GOG a seleção `ID interno -> bloco físico` e `RANK -> matriz 1/2/3`, validando com bytes reais. Não inferir pelo índice dos nomes. Considerar mudanças de endereços entre mods/emuladores. Adicionar adaptadores baseados em evidência, testes e UI clara. Uma meta técnica é dispensar registros manuais de drop durante jogos.

**Depois de comprovar IDs/ranks:** implementar drops oficiais por ISO, revisar fusões, tipos especiais (mágicas/equips/traps/rituais), efeitos, MIPS e atualizador/launcher. Garantir regressão de todas as 722 cartas e artes do GOG. Não fazer merge automático em main.

## 8. Regras e decisões de produto

- Preservar UX PT-BR e visual moderno navy/ciano/dourado. Home limpa: mão, fusões, RANK; diagnóstico na Biblioteca de Mods.
- Dados de cartas, artes e pesos só da ISO ativa; NUNCA inventar drops, fusões, nomes, IDs, efeitos nem taxa de RANK; rotular dados ainda hipotéticos.
- Somente leitura de RAM; não escrever na memória do emulador. Caminhos, chaves, ISO original, executáveis extraídos, artworks proprietários e dumps não vão ao GitHub, CI ou exportações.
- Não criar conexão de telemetria/streaming remoto silenciosa; exigir consentimento explícito e autenticação.
- Código fonte público no repositório atualmente (verificado pelo conector em 06/11/2026). Considerar estratégia de licenciamento e proteção intelectual separadamente.
- PRs em draft; conferir CI e release reais antes de recomendar atualização. Commit imutável de referência é mais confiável do que seguir `main`.
- Após cada etapa atualizar o contexto da Biblioteca e gerar um backup independente.

## 9. PROMPT PARA A PRÓXIMA CONVERSA

> Continue o projeto DUELTRACE de onde parou. Leia na Biblioteca `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/` e dê prioridade ao backup **Etapa25 Live Diagnostics (06/11/2026)**, não aos documentos antigos que param na Etapa15. Repositório `https://github.com/guibatoni/appassist`, PR #73, branch `feature/dueltrace-v097-live-diagnostics-v25`, commit testado `089d6773e3d7be92afbd7b6442b814f2d8b611a7`, Preview `preview-v0.9.7-r42283346075`, CI 754 testes e Windows OK. A Biblioteca tem 722 cartas/atributos e artes funcionando, e a leitura de 5 cartas de mão está correta. GOG tem 39 nomes estruturais, 40 blocos / 160 matrizes; IDs e drops/RANK não mapeados. Etapa25 adicionou coleta opcional local com relatório JSON seguro em Biblioteca de Mods. Primeiro analise um relatório real deste painel (se disponível); concentre-se no bug da detecção de ID de adversário usando a âncora pela mão comprovada, depois resolva via MIPS o mapeamento ID->bloco->grupo RANK. Preserve o que funciona, não peça duelos manuais repetitivos, nunca libere drops por hipótese, não faça merge em main sem autorização, atualize o backup a cada etapa.

## 10. Natureza do backup

Este documento conserva **decisões, estado e referências imutáveis**; não contém bytes da ISO nem instalação Windows completa. Para restaurar o código use o snapshot do GitHub no commit fixo. Para instalar use a release indicada. Para preservar evidências antigas use os arquivos preexistentes da pasta da Biblioteca e seus ZIPs de Etapas 5–15.
