# DUELTRACE v0.9.5 — Evidências provisórias de drops em novos mods

**Base:** PR #44, v0.9.4, commit `a752d805d4f2b7807e133ce1cc615a98034f74ed`.
**Branch:** `feature/dueltrace-v095-partial-iso-evidence`.
**ISO analisada pelo usuário:** GOG MOD 2.2 – Drop 15 (NDC), SHA-256 prefixo `61d58d83524683c8dc...`.

## Evidência da captura do GOG

A v0.9.4 encontrou `GOG_VNT.223` com cabeçalho `PS-X EXE` e `GOSD/GOG_SD1.23`, arquivo renomeado do mesmo tamanho do WA tradicional. O scanner gerou **117 tabelas estruturais e 4.543 registros de drops**, mas **0 cartas e 0 oponentes verificados**. A base de nomes SLUS não passou nas validações de identidade e não é correto deduzir os IDs e os grupos de RANK só pelo somatório dos pesos.

O scanner antigo usava `weights_ok` para promover automaticamente as 117 tabelas em `importador_perfis.py`, mesmo quando `card_ok` e `opponent_ok` eram falsos. A API e a interface exibiam 4.543 **Drops** como se fossem prontos para uso.

## Mudança aplicada

- Separar `weights_structural_ok` (117 matrizes com soma 2048 e entradas) de `weights_ok` (essas matrizes **mais** catálogo de 722 cartas e 39 oponentes verificados).
- Quando não é possível mapear as identidades, salvar em `drops_provenance`: `candidate_table_count`, `candidate_entry_count`, `candidate_weight_total`, origem WA, SHA da ISO e indicação de nomes/ranks não confirmados. Não publicar os registros no perfil `drops` nem liberar `supported_features.drops`.
- O scanner já escreve os dados brutos em CSV local por SHA; a evidência **não é descartada**, mas não pode ser usada pelo cliente em Drops/RANK até a identidade ser verificada.
- Biblioteca de Mods mostra os valores separados: **Drops confirmados** / **Tabelas WA confirmadas** e **Drops provisórios: 4.543 entradas em 117 matrizes**. A quantidade mostrada depende de cada perfil, não é um valor fixo.
- Para Original, FM13 ou Remaster X15 **com catálogos completos**, o comportamento de mapeamento estrutural continua como antes. Apenas o SHA-256 exato do Remaster X15 usa Z-POW/S-POW/S-TEC; demais mods mantêm dez ranks clássicos, sem prometer que a distribuição da ISO foi confirmada em duelo.
- Testes sintéticos demonstram a quarentena de drops GOG, manutenção da leitura completa com catálogos válidos, distinção das regras X15 e corrupção de pesos.

## Limitações / próximos passos

Ainda **não** recuperamos os 39 nomes dos oponentes nem verificamos os nomes/atributos das 722 cartas no executável `GOG_VNT.223`. O processo correto é:

1. Reanalisar GOG após a v0.9.5 e verificar as amostras do diagnóstico `amostras_layout_nomes` para cartas/oponentes; comparar com nomes exibidos no próprio jogo.
2. Se os nomes das cartas estiverem íntegros mas a tabela de oponentes tiver sido realocada, procurar **ponteiros deslocados** ou outro mapeamento de glifos com validação de várias amostras e limites de tempo/memória.
3. Desenvolver um adaptador específico de estrutura de nomes para essa ISO, com limites, SHA e testes; validar os 39 adversários e 722 cartas antes de ligar os IDs às 117 matrizes.
4. Confirmar a ordem dos grupos e as probabilidades de drops do mod em duelos reais; os pesos podem ser estruturalmente plausíveis sem representar a tabela correta.
5. Somente depois tentar artes, fusões, efeitos e localização das rotinas de RANK. Preservar leitura de mão e o cálculo de Spoils já comprovado.

## Prompt de continuidade

> CONTINUAR DUELTRACE v0.9.5. Repo: https://github.com/guibatoni/appassist. Branch `feature/dueltrace-v095-partial-iso-evidence`. Na ISO GOG MOD 2.2 (prefixo SHA 61d58d83524683c8dc), a v0.9.4 encontrou `GOG_VNT.223`, `GOSD/GOG_SD1.23`, 117 matrizes WA e 4.543 entradas de drops, mas NÃO encontrou cartas nem oponentes validados. Na v0.9.5, os drops são preservados como **candidatos estruturais** com contadores separados da lista de drops confirmados; o RANK continua indisponível até identidade e RAM confirmadas. Próximo objetivo: descobrir e validar a localização real das tabelas de nomes de cartas e oponentes do GOG, com sondagens limitadas e evidência do jogo, antes de reabilitar drops/arte/fusões. Nenhum LLM pode inventar nomes, offsets ou confirmar identidade. Preservar Original/FM13/X15, perfis por SHA, atualizador e segurança. Ao final, registrar commit, PR, CI, testes e pendências.
