# DUELTRACE v0.9.1 — correção da confirmação de LP e continuidade do RANK

Base: v0.9.0, PR #40, commit `b80b776c32296d26833058b23e0b7357bf150df6`.
Branch: `feature/dueltrace-v091-live-rank-calibration`.

## Diagnóstico da imagem recebida

O ePSXe apresentava 10000 LP, e o DUELTRACE exibia 10000 no input do painel RANK, porém o botão Confirmar estava desativado. O campo usava `placeholder={candidateLp}` com `value=""` e a ação exigia `!lp`. Placeholder não é valor; o leitor tinha retornado um candidato plausível, mas o usuário não podia confirmar sem redigitar todo o número.

Essa é uma falha real da interface, não uma prova de que a fórmula de SPOILS estava incorreta.

## Correção

- O input passa a **usar o candidateLp como valor inicial real**, sem exigir digitação, mantendo capacidade de corrigir o valor. O usuário deve **comparar** esse número com o HUD do ePSXe e clicar em **Confirmar LP** uma vez.
- O clique confirma o valor no backend via API tokenizada. **Não** há confirmação silenciosa de um único endereço RAM não verificado; isso evitaria falsos RANKs.
- Depois da primeira calibração, o leitor atualiza o score automaticamente a cada 850 ms, após observar duas transições coerentes da RAM quando a ISO usa sondagem experimental. O painel permanece compacto, com cartas na mão, dicas de fusão e RANK.
- Uma única leitura instável no **mesmo PID e mesma ISO** não força nova confirmação imediata: a calibração é conservada por até **2,5 s**, sem exibir score antigo. Gap maior, PID diferente ou memória inconsistente invalidam a calibração.
- Após confirmar LP, uma próxima partida na **mesma sessão ePSXe**, mesma ISO selecionada, mesmo PID e exatamente o mesmo valor inicial de LP pode reaproveitar a confirmação quando os turnos reiniciarem. Uma troca de LP inicial, processo, mod ou leitura incoerente exige nova confirmação.
- Nenhuma mudança na fórmula nem na classificação: dez RANKs clássicos para todas as ISOs não-X15; três rótulos Z-POW/S-POW/S-TEC só para SHA do Remaster X15.
- A leitura em outros mods continua **experimental**: duas transições plausíveis e LP manual conferido não confirmam a rotina do SLUS nem garantem que o ePSXe abriu a ISO selecionada. A projeção experimental não valida bindings nem autoriza capturas oficiais.

## Testes

- X15: durante uma falha temporária de RAM, o score some imediatamente, mas a calibração permanece se a mesma instância do ePSXe voltar em até 2,5 s.
- Outra instância ou falha maior reseta a confirmação.
- ISO não-X15: HUD 10000 LP, confirmação, uma mudança de contador, falha de um frame, segunda mudança → RANK provisório com letra original.
- Novo duelo com os mesmos LP/PID/ISO reaproveita a calibração; LP diferentes e troca do PID exigem confirmar novamente.
- Next.js deve compilar com input controlado e botão ativado pelo valor candidato; a CI Windows deve passar antes do lançamento.

## Pendências

- Testar em Windows/ePSXe real e confirmar que o input agora mostra 10000 como valor editável e ativa o botão, diferentemente do placeholder.
- Confirmar a correção das oscilações de RAM e o novo duelo no ePSXe.
- Validar o endereço RAM antigo e fórmula numérica em Original/FM13 com partidas independentes; jamais afirmar compatibilidade universal sem esses testes.
- Automação 100% sem qualquer clique ainda requer evidência independente do LP do HUD ou leitor validado da mesma ISO; não substituímos isso por suposições.
- Preservar scanner, Biblioteca, Drops, Fusões, imagens, atualizador com SHA-256 e dados locais.

## Próximo prompt

> CONTINUAR DUELTRACE v0.9.1, repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v091-live-rank-calibration`. Corrigido o defeito da v0.9.0: input LP tinha placeholder 10000, value vazio e botão desativado. A UI agora coloca candidateLp como valor do campo, editável, permitindo confirmar com um clique após comparar ao HUD. O leitor experimental continua calculando automaticamente e exibindo somente rank clássico fora do X15, após duas transições plausíveis. Mantém a calibração por até 2,5 s em breves gaps de RAM do mesmo PID sem exibir score antigo. Nas próximas partidas com mesma ISO, mesmo ePSXe e LP inicial idêntico, reaproveita confirmação de LP dentro da sessão; LP/PID diferentes exigem nova conferência. Não altera fórmula nem modelos, não transforma sondagem em binding RAM validado. Validar CI e testes, aplicar no Windows/ePSXe e investigar se a estrutura do mod realmente corresponde ao endereço legado. Registrar versão, PR, commit, CI, testes e pendências.
