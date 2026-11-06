# DUELTRACE — Etapa 26: evidências da âncora da mão versus campos legados

Data: 2026-11-06. Base: Etapa 25, PR #73, commit testado `089d6773e3d7be92afbd7b6442b814f2d8b611a7`; branch da Etapa 25 na criação: `fdaec9dc4ab2dcf002d92a2dd85fbe8bea336107`.

## Problema observado no código (não é prova do comportamento no PC)

A sonda `_valid_psx_sample` comparava a mão no endereço comprovado do leitor clássico com a mão candidata da RAM, mas somente contabilizava `validatedHandAnchors` depois das validações de ID e LP. Logo, um acerto da mão acompanhado de LP inválido ou byte do oponente ilegível deixava de aparecer como acerto da âncora. Isso ocultava uma distinção importante para a engenharia reversa do GOG.

## Alteração restrita e reversível

1. `scanner/dueltrace_live_opponent.py`: contabiliza a âncora válida assim que encontrada, mesmo que os offsets legados de LP/ID falhem. A avaliação completa continua exigindo os mesmos requisitos; **não relaxa aceitação de ID**.
2. Se a tentativa no endereço inferido pela mão falha, o resultado inclui `knownHandAnchorAtHint` e `hintValidationBreakdown`; endereços e bytes não são enviados à interface.
3. `scanner/dueltrace_live_diagnostics.py`: exporta apenas o booleano `knownHandAnchorAtHint` e contadores numéricos conhecidos em `hintRejectionCounts`. Desconhecidos são descartados. Mantém a sonda como provisória e não ativa drops/RANK.
4. Testes sintéticos adicionados para âncora válida com LP inválido, byte do ID ilegível, e privacidade/sanitização. **Testes no emulador real e CI da Etapa 26 ainda precisam de confirmação.**

## Protocolo para um único teste real

1. Confirmar que o GOG MOD 2.2 - Drop 15 (NDC) está ativo no DUELTRACE e aberto no ePSXe.
2. Iniciar `Biblioteca de Mods → DUELTRACE Live Diagnostics → Iniciar diagnóstico` e jogar uma sessão normal. Não repetir preenchimento manual de drops.
3. Parar diagnóstico, copiar JSON e enviar para análise. Verificar especialmente `hand.ready`, `opponent.status`, `knownHandAnchorAtHint`, `hintRejectionCounts` e `rejectionCounts`.
4. Se `knownHandAnchorAtHint=true` e `implausibleLifePoints>0`, investigar offset/formato de LP no GOG, **sem concluir que o byte do ID é válido**. Se `unreadableFields>0`, investigar acessibilidade e offset. Se `knownHandAnchorAtHint=false`, investigar endereçamento/instância do ePSXe.
5. Só associar nomes estruturais, IDs internos, blocos físicos e RANK com evidência de execução MIPS ou de múltiplos sinais independentes. Não ativar drops pela mera observação.

## Restrições

Biblioteca 722/722, artes e leitor da mão permanecem intactos. Não incluir ISO, conteúdo RAM, artes ou endereços do PC em relatórios. Não fazer merge na main. A Etapa 25 continua como base verificável; a Etapa 26 não substitui confirmação do CI/Windows/ePSXe.

## Primeiro relatório real recebido em 06/11/2026 (observação, não calibração)

Foi recebido um JSON de Live Diagnostics com `romFingerprint=61d58d835246`, `sampleCount=30`, `changeCount=15`, 15 alterações de mão legíveis, 15 de adversário legíveis, todas com `status=runtime_id_candidate`, `candidateId=5` e `mappingMethod=known_hand_anchor`. No recorte houve dois pares de LP: jogador/adversário `5408/10023` e `3879/1062`. Não houve RANK legível; `verifiedOpponentMapping=false`, `verifiedRankGroups=false`.

**Confirmação limitada:** o byte **candidato** 5 permaneceu consistente nos 15 eventos de mudança que o monitor gravou nessa sessão e a sonda utilizou o ancoramento pela mão. Não confirma o oponente nomeado, ID de tabela do executável, identidade da ISO carregada dentro do ePSXe, bloco físico, RANK nem drops. O fingerprint da ISO ativa no DUELTRACE não é uma checagem independente do disco montado no emulador.

**Correção complementar:** a exportação recebida possuía `knownHandAnchorAtHint=false` ao mesmo tempo que `mappingMethod=known_hand_anchor`. O caminho bem-sucedido por hint não preenchia aquele booleano, e o saneador adotava `false`. Corrigido o campo no caminho rápido, acrescentado `handAnchorValidated` no evento e adicionadas métricas descritivas `candidateEvents`, `candidateIdsObserved`, `candidateIdStableAcrossReadableChanges`, `handAnchorValidatedChanges`, `distinctLpPairsInReadableChanges`. Estabilidade se refere **somente às mudanças legíveis gravadas em uma sessão**, sem autorização para associar nomes ou liberar drops.

O relatório foi guardado como evidência do usuário na Biblioteca (não commitamos log de sessão ou ROM em repositório público). Verificação da execução real da versão com correção e pipeline Windows da nova HEAD ainda depende de CI e execução.
