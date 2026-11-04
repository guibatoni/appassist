# DUELTRACE v0.8.9 — Central de Duelo enxuta e RANK ao vivo honesto

**Base:** v0.8.8, PR #38, commit `622235469abc9dece578a3247abcda23545c7a2a`.  
**Branch:** `feature/dueltrace-v089-clean-live-duel`.

## Solicitação do usuário

> "não está fazendo o calculo automatico. Otimize e limpre a area inicial está muito poluido de informações. Nosso foco para area é as cartas que constam na mão, dicas de fusões e o contador de rank ao vivo."

## Alterações

- A aba **Início / Central de Duelo** exibe apenas três seções principais: **Cartas na mão** (cinco slots, atualização a cada 1,5 s), **RANK ao vivo** (atualização a cada 2,2 s) e **Dicas de fusões** (duplas/cadeias até 5 cartas).
- O RANK foi movido para um painel compacto ao lado da mão em telas largas, com score, letra, estado de conexão e, quando disponíveis, LP/turnos/fusões. Ferramentas avançadas e captura de previsão continuam acessíveis em um elemento *expandível*, sem ocupar espaço da experiência normal.
- O painel redundante **Calculadora automática de Spoils** com 101 fictícios e dez contadores de demonstração foi removido da tela inicial. **101 continua sendo a projeção matemática de abertura**, mas não é apresentado como resultado ao vivo quando a RAM não está calibrada.
- O motor backend continua consultando a memória automaticamente para ISOs com binding autorizado; a confirmação de LP permanece como verificação pontual de leitura, não como preenchimento de ações.
- Se a ISO ativa não possui tabela RANK/SLUS ou binding RAM validado, o painel informa claramente **Sem pontuação lida da RAM**, sem inventar score. Em ferramentas avançadas, **Diagnosticar ISO** e **Reanalisar perfil** (apenas se tabela ausente) estão disponíveis.
- O painel de fusões mostra as seis primeiras sugestões para evitar poluição, com opção **Ver todas**. Mantém as duas modalidades (duplas/cadeias), validação e stats.
- O backend conserva somente **um cache da mão atual + perfil SHA/revisão de fusão** para evitar reexecutar a busca exaustiva de cadeias a cada atualização periódica. Recalcula ao mudar a mão ou atualizar o perfil do mod. Os cards lidos da RAM continuam atualizados por chamada.
- `get_rank` fornece `rankSystem` mesmo quando o perfil é recusado, para deixar explícita a classificação original em ISO não-X15.
- Foram adicionados testes de cache de fusão e garantia de que RANK desabilitado nunca retorna 101 como pontuação lida.

## Importante: o que continua bloqueado

A captura e a pontuação automática dependem de **endereços RAM validados para a ISO ativa**. A imagem enviada pelo usuário mostrava `rank_table_missing`; isso não é um bug de React e não pode ser resolvido apenas com estilos ou reutilizando 0xB41990 do X15 em qualquer mod.

Sem a ISO exata, o processo ePSXe e observações de ações em duelo, não é possível confirmar outro binding RAM. É obrigatório comparar hashes ROM/SLUS/tabela, LP do jogo e movimentações de contadores. O Remaster X15 conhecido já possui o leitor candidato restrito, com verificação de LP; mods Originais/FM13 sem perfis validados continuam com indicação de bloqueio, não score falso.

## Plano de validação

- Verificar compilação Next.js, suíte Python inteira, auditoria de segurança Windows, criação e publicação da nova Preview no GitHub Releases.
- Validar no Windows real: cinco cartas aparecem na Central; atualizar mão muda sugestões; RANK da ISO autorizada atualiza a cada ~2,2 s após confirmação LP; RANK de ISO não mapeada continua indisponível, porém oferece diagnóstico e reanálise.
- Testar Remaster X15, Original e FM13 separadamente; confirmar qual ISO o ePSXe carregou antes de afirmar compatibilidade; investigar diferenças históricas de pontuação e classificação, sem alterar fórmula numérica arbitrariamente.

## Prompt de continuidade

> CONTINUAR DUELTRACE v0.8.9, repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v089-clean-live-duel`. A Central de Duelo agora prioriza cinco cartas da mão, sugestões de fusão (duplas e cadeias 2–5) e um Contador de RANK ao vivo compacto. A calculadora de demonstração de Spoils e 101 pontos hipotéticos saíram da tela. Leitura de mão e RANK são consultadas periodicamente; sugestões de fusão são armazenadas até a mão ou o perfil mudar. Diagnósticos e captura estão recolhidos, RANK permanece sem pontos quando a ISO não tem RAM validada, com reanálise de perfil opcional se a tabela WA não foi encontrada. CONFIRMAR PR/HEAD/CI antes de afirmar os testes. Próximo objetivo é testar Windows/ePSXe com a ISO selecionada e construir/verificar seu binding RAM para liberar RANK realmente automático em FM13/Original, sem herdar endereços X15 sem evidência. Preservar fórmula, classificação X15 vs original, Drops, Biblioteca, Fusões e atualizador sem assinatura obrigatória com SHA-256. Registrar versão, branch, commit, PR, CI, testes e pendências.
