# DUELTRACE v0.8.8 — Herança do Assistente X15 v10.5 e RANK original por ISO

**Base:** v0.8.7, PR #37, commit `0fed9f3c50b8cb4828bfdd9121a74901c8d54891`.  
**Branch:** `feature/dueltrace-v088-legacy-rank-original`.  
**Fonte local examinada:** `Assistente_X15_v10_5_ISO_INTEGRADA(1).zip`, em especial `spoils_x15_core_v8.py`, `tabela_spoils_x15.json`, `painel_spoils_x15_v8.py` e seus autotestes. Nenhuma ROM ou imagem do usuário foi enviada ao repositório.

## Confirmações da investigação antiga

O Assistente usa o núcleo extraído do Remaster X15 1.2.1:

- Base do score: **50**.
- Dez critérios, com limiares exclusivos; os dez conjuntos de limiares/pontos são numericamente idênticos aos `RULES` existentes no DUELTRACE.
- Vitória por LP **+2**, por deck-out **−40**, Exodia **+40** (Exodia NÃO possui marcador RAM validado para reconhecimento automático).
- Decodificação de registro de duelo de **32 bytes**: os contadores de ações são `u8`; LP em `+20` é `s16le`; cartas usadas em `+24` são `s8`; ajuste do resultado em `+0` é `s8`.
- Filtros de plausibilidade migrados: cartas usadas entre 0 e 40; turnos entre 0 e 80; ações individuais até 60; rejeição de registro zerado e incoerente com LP zero. Esses filtros reduzem falsos positivos mas não confirmam endereço RAM.
- Valores de resultado usados pelo Assistente: byte `0x02` = `+2` LP; byte `0xD8` = `−40` deck-out; `0x00` não comprova vitória. Não inferir Exodia por bytes não mapeados.
- Exemplo hipotético de abertura: `50 + 49 + 2 = 101`. A pontuação calculada é distinta de uma pontuação oficial lida na RAM; nunca apresentar equivalência sem comprovação independente.
- O executável X15 contém comparações de faixa **50** e **95** para os três nomes próprios: `Z-POW` >=95, `S-POW` 50–94, `S-TEC` abaixo de 50.

## Integração implementada

1. `dueltrace_rank_live.decode_rank_result_adjustment`: lê o primeiro byte de **uma amostra de 32 bytes** como `s8`, aceitando apenas `2` e `-40`.
2. `read_rank_candidate`: exige **duas amostras estáveis e idênticas incluindo marcador**. Em transição retorna leitura indisponível; não retorna contadores desatualizados.
3. `project_spoils_with_adjustment`: aplica o bônus observado à **mesma fórmula e aos mesmos critérios**, mantendo o score numérico e o detalhamento; `project_lp_win_rank` permanece compatível como previsão de LP `+2`.
4. `get_rank`: **somente quando a ISO selecionada tem o SHA exato do Remaster X15**, pode aplicar o marcador RAM assinado à pontuação. Em qualquer outro mod, inclusive com binário idêntico ao X15 ou título contendo `X15`, o marcador específico **não** é utilizado.
5. Toda classificação exibida é calculada com `rank_label_for_existing_score(sha,score)`, usando **os dez RANKs originais** para Original, FM13 e demais mods não-X15; apenas o X15 exato recebe os três RANKs Z/S/S. A mesma separação já rege os filtros e os três bancos de drops.
6. O painel de Spoils informa explicitamente `Sistema original · 10 classificações` ou `Remaster X15 · 3 classificações`; informa se o estado é previsão futura por LP ou marcador LP/deck-out identificado na RAM.
7. **Não** identifica automaticamente qual ISO o ePSXe realmente abriu. A seleção do aplicativo ainda deve ser confrontada com o jogo. O marcador RAM é evidência local, não comprovação isolada do resultado oficial; `final` continua falso.
8. Continua exigindo LP confirmados e mapeamento RAM autorizado para pontuação ao vivo. Mods sem binding validado mantêm apenas a referência hipotética e não passam a ler endereços X15.

## Faixas do RANK original (dez)

| Pontos | Nome |
|---|---|
| >=90 | S-POW |
| 80–89 | A-POW |
| 70–79 | B-POW |
| 60–69 | C-POW |
| 50–59 | D-POW |
| 40–49 | D-TEC |
| 30–39 | C-TEC |
| 20–29 | B-TEC |
| 10–19 | A-TEC |
| <=9 | S-TEC |

**No Remaster X15 exclusivamente:** >=95 Z-POW, 50–94 S-POW, <=49 S-TEC.

## Testes de regressão

Novo `tests/test_dueltrace_legacy_rank_transfer.py`: paridade exata dos dez critérios contra a tabela v10.5, offsets e sinal dos campos, byte `0xD8` como `-40`, exigência de duas leituras idênticas, bônus LP/deck-out/Exodia e todas as fronteiras dos dez RANKs clássicos.

Expandido `tests/test_dueltrace_rank_capture.py`: com ISO X15, marcador deck-out muda o score **101→59**, sem declaração de nota final oficial; com SHA distinto mas binário/tabela numéricos compatíveis, score **101→87** continua apresentando **S-POW→A-POW** do original, ignorando marcador X15 e sem Z-POW.

Os testes usam registros RAM **sintéticos** e não executam o jogo. A CI Windows deve passar antes de publicar a versão.

## Pendências

- Testar X15 em Windows/ePSXe e registrar evidência dinâmica de byte `+0` (0→2 ou 0→0xD8) e dos dez critérios no mesmo processo.
- Confirmar limites e comportamento de grade com resultado real no jogo, incluindo discrepâncias históricas de 50 pontos / S-TEC e 46 calculado / 45 observado.
- FM13/Original precisam de validação independente de RAM/SLUS/tabela para cálculo automático; **não** assumir mesmos endereços do X15.
- Confirmar que a ISO realmente executada no emulador corresponde ao SHA selecionado no DUELTRACE.
- Preservar scanner, biblioteca, fusões, catálogo Drops, molduras, atualizador verificável sem assinatura obrigatória e dados locais.

## Prompt de continuação

> CONTINUAR DUELTRACE v0.8.8. Repo https://github.com/guibatoni/appassist, branch `feature/dueltrace-v088-legacy-rank-original`. A fórmula numérica herdada do Assistente X15 v10.5 confirmou as dez tabelas e a base 50, LP +2, deck-out -40 e Exodia +40. O código agora lê byte assinado +0 de duas amostras estáveis da ISO **X15 exata**: 0x02→+2 e 0xD8→−40. Não assume Exodia por RAM. O DUELTRACE exibe os **dez RANKs originais** em todos os demais mods, enquanto o Remaster X15 reconhecido por SHA usa somente Z-POW/S-POW/S-TEC. O RANK no painel indica se veio de previsão LP ou marcador X15 detectado, sem afirmar nota oficial lida na RAM. Preserve filtros Drops, fórmula, segurança, atualizador e dados locais. Valide com ePSXe real e compare com as telas oficiais, especialmente 50 S-TEC e diferenças de 1 ponto. Confirme PR/HEAD/CI antes de citar números de testes. Ao concluir forneça versão, branch, commit, PR, CI, testes e pendências.
