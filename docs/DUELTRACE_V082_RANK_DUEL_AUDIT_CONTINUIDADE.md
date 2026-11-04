# DUELTRACE v0.8.2 — Auditoria offline do RANK por duelo

Data: 03/11/2026. Base: commit `30413efa500aa784cb8cadc66689f5ee8cd62605` (v0.8.1, PR #31).  
Branch: `feature/dueltrace-v082-rank-duel-audit`.

## Objetivo e alteração

A fórmula original, os contadores RAM, os bônus de vitória, a classificação conforme SHA e o requisito de confirmar LP **não foram modificados**. A auditoria exportada por `export_rank_audit` agora inclui `rank_comparison`, gerado por `scanner/dueltrace_rank_duel_verification.py`.

São comparados apenas resultados observados manualmente na ISO selecionada com o snapshot de previsão provisória *se vencer por LP* do mesmo registro de duelo. Não há acesso ao ePSXe a partir do comparador, nem reconhecimento automático do arquivo aberto pelo emulador.

- `match`: score numérico e classificação coincidem.
- `score_mismatch`, `rank_mismatch`, `score_and_rank_mismatch`: divergências explícitas.
- `rank_only_match` / `rank_only_mismatch`: sem pontuação observada, compara somente letras (evidência parcial).
- `not_lp_win`: deck-out ou outra condição, não comparável com projeção de LP.
- `missing_prediction`, `invalid_snapshot`, `invalid_observation`, `observed_result_conflict`, `duplicate_duel`: não utilizáveis para corroborar previsão.

Os registros exportam no máximo 50 casos de comparação, sem contadores RAM, caminhos locais, ISO ou logs brutos. O sumário conserva contagem de todos os registros incluídos até o limite de 500.

A própria comparação permanece manual e **não valida execução MIPS, mapeamento RAM, identidade da ISO aberta, fórmula ou causalidade**. Não promove automaticamente mods para status validado. O uso do modo ao vivo continua condicionado às proteções da v0.8.1.

## Testes

`tests/test_dueltrace_rank_duel_verification.py`: sistema X15/clássico, igualdade numérica, diferenças de score, comparação só da letra, snapshots ausentes ou inválidos, deck-out, conflito no resultado observado, duplicidade, isolamento entre hashes e ausência de dados privados na exportação.

Executar toda a suíte no CI Windows e inspecionar o artefato de segurança. Não declarar validação em ePSXe sem realizar duelos reais com as ISOs X15, FM13 e Original. Nem a CI nem dados de teste substituem prova dinâmica do jogo.

## Procedimento para validação humana

1. Selecionar e verificar o SHA da ISO local no DUELTRACE. Confirmar separadamente qual ISO foi carregada no ePSXe.
2. Durante duelo com modelo de RANK autorizado, confirmar LP exatos e capturar a projeção no final do duelo, antes da transição. Registrar se o jogo terminou por LP ou deck-out.
3. Informar no aplicativo o adversário, RANK apresentado pelo jogo, pontuação se visível e carta recebida, sem inventar pontos ausentes.
4. Exportar relatório JSON de auditoria e consultar `rank_comparison`.
5. Comparar ao menos duas partidas independentes por combinação ROM/SLUS/tabela e conferir mudanças reais dos contadores; somente depois investigar bindings ausentes. Duas partidas coincidentes por si só não provam MIPS.
6. Em mods sem binding, confirmar estado `unsupported` sem score ou RANK ao vivo. Não remover esse bloqueio.

## Pendências

- Executar duelos reais no Windows/ePSXe: Remaster X15, FM13 e Original.
- Verificar hashes ROM/SLUS/tabela, memória host, rastreamentos MIPS e alterações de contadores por sessão.
- Integrar identificação comprovada da ISO executada no emulador sem inferir pelo nome; a seleção no catálogo ainda é independente.
- Avaliar divergências com logs e telas reais sem publicar material do jogo.
- Preview Windows ainda é não assinada. Não contornar antivírus/SmartScreen.
- Preservar scanner, biblioteca, fusões, drops, molduras, atualizador, controles de segurança.

## Prompt de continuidade

> Continue o DUELTRACE a partir da v0.8.2 no repositório https://github.com/guibatoni/appassist e branch `feature/dueltrace-v082-rank-duel-audit`. A v0.8.1 (PR #31) manteve os pontos e mudou somente a classificação pela ISO. A v0.8.2 adiciona um comparador offline por duelo ao relatório exportável: diferencia correspondência integral, divergências, rank somente, deck-out, snapshots incompletos e dados inválidos. Não recalcula o score nem altera RAM/MIPS. Confirme o PR, HEAD e CI antes de citar testes aprovados. Próxima tarefa: testar com duelos reais Remaster X15, FM13 e Original no ePSXe, conferindo a identidade da ISO executada, LP, pontuação, RANK exibido e vínculo RAM/trace. Mods não verificados permanecem bloqueados. Não declarar fórmula MIPS confirmada sem prova dinâmica independente. Preservar UI, scanner, biblioteca, fusões, drops, molduras, atualizador seguro e não publicar material de ROM. Ao encerrar, registrar nova versão, branch, commit, PR, CI, testes e pendências.
