# DUELTRACE v0.8.4 — Diagnóstico de RANK bloqueado

Data: 04/11/2026 (Brasil).
Repositório: https://github.com/guibatoni/appassist
Base: v0.8.3, branch `feature/dueltrace-v083-updater-rank-capture`, PR #33, commit `70227b5dc8bba242885feb10e492010889f99562`.
Branch atual: `feature/dueltrace-v084-rank-diagnostic`.

## Problema observado

Na Central de Duelo, a interface exibia **RANK indisponível** e o botão de captura estava desativado, com o status "Tabela e/ou rotina de RANK ainda não calibradas para esta ISO." Não se trata de um botão quebrado: `scanner/dueltrace_web_bridge.py::_rank_sample()` impede previsão sem uma das condições estritas:

- Hash exato da ISO X15 conhecida.
- Binding de ROM/SLUS/tabela/RAM validado em duelos independentes.
- Compatibilidade binária exata com o executável e a tabela X15 verificados.

**Nenhum mod foi autorizado artificialmente.** MIPS estático e extração da tabela WA não comprovam execução nem contadores.

## Implementado

- Novo diagnóstico read-only `scanner/dueltrace_rank_diagnostic.py`, com motivos e próximos passos legíveis por usuário.
- `get_rank_diagnostic` na bridge + proteção com token em `ProtectedDesktopApi` + cliente tipado.
- A Central de Duelo oferece **Diagnosticar RANK desta ISO**, mesmo que o botão "Capturar previsão de RANK" esteja desativado.
- O diagnóstico mostra prefixo SHA da ISO selecionada, se a tabela WA foi detectada, se sua estrutura foi conferida, quantidade de PCs candidatos, vínculo RAM validado e se modelo X15 exato está disponível.
- Ação de navegação **Registrar RANK final em Drops**, para observações manuais de partidas sem pontuação ao vivo.
- Testes sem ROM real em `tests/test_dueltrace_rank_diagnostic.py`: hash X15, perfil desconhecido, tabela ausente, MIPS candidato não validado, binding ausente/ inválido/ validado, autorização de API e ausência de pontuação fabricada.

## Proteções mantidas

A fórmula do score da v0.8.1 permanece integralmente igual; as bandas de classificação por ISO permanecem iguais; não há nenhuma alteração nos leitores de RAM, mapeamento MIPS, scanner, fusões, biblioteca, drops, molduras, atualizador ou políticas de assinatura. Para mods sem binding comprovado, nenhuma pontuação ou RANK são projetados. O botão de captura permanece desabilitado nessa condição.

## Validação do mundo real

Ainda pendente: selecionar ISO no DUELTRACE, confirmar qual ISO o ePSXe carregou, confirmar LP, capturar previsão no fim de duelo com modelo autorizado e comparar com RANK e pontuação exibidos na tela final. Executar em Remaster X15, FM13 e Original. Para FM13 ou Original sem binding, usar observações manuais e traces (opcionais) em Drops; comparar evidências antes de autorizar um modelo.

A mensagem de diagnóstico explica o bloqueio, mas não prova a fórmula MIPS. A Preview Windows continua sem assinatura digital e não deve auto-instalar por cima de outra versão não assinada.

## Próximo prompt

> Continue DUELTRACE v0.8.4 a partir da branch `feature/dueltrace-v084-rank-diagnostic` no repositório https://github.com/guibatoni/appassist. Conferir HEAD, PR e CI antes de citar números de testes. Implementamos diagnóstico read-only quando RANK está indisponível: motivos precisos para tabela WA ausente, candidatos MIPS sem RAM validada, binding ausente/inválido e hash X15 conhecido. A UI oferece botão 'Diagnosticar RANK desta ISO' habilitado mesmo com o contador bloqueado e navegação para registrar RANK final manualmente em Drops. Não habilite captura sem pontuação autorizada. Próximo objetivo: validar com duelos reais no ePSXe com X15, FM13 e Original, obtendo provas de mapeamento de RAM da ISO ativa e rastros MIPS dinâmicos, sem herdar endereços por nome. Preservar fórmula numérica, classificação por ISO, scanner, biblioteca, fusões, drops, UI e segurança. Finalize com versão, branch, commit, PR, CI, testes e pendências.
