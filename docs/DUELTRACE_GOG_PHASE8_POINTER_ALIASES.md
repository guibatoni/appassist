# DUELTRACE — Etapa 8: aliases de ponteiros nos nomes dos adversários

## Evidência observada no GOG MOD 2.2

A captura `GOG MOD 2.2 - Drop 15 (NDC).iso` mostra:
- **722 cartas** extraídas do executável; IDs ainda não confirmados em jogo;
- **até 39 nomes candidatos**, mas sem adversários publicados;
- mensagem da revisão 22: **"A tabela contém endereços repetidos; os possíveis aliases ficam em investigação."**
- Fusões e drops ainda desconhecidos.

Essa mensagem prova que a tabela **candidata** possui ponteiros repetidos, mas não demonstra se são aliases legítimos do mod ou uma janela indevida.

## Scanner revisão 23

O `dueltrace_opponent_boundary_probe.py` distingue três situações:

1. **Aliases estruturalmente coerentes:** entre os 39 índices, no máximo dois
   reutilizam endereços existentes. São exigidos pelo menos **37 registros
   físicos distintos**, as fronteiras reais entre eles, terminador igual,
   preenchimento seguro, diversidade de nomes e apenas **uma janela completa**.
   Uma sequência elegível pode ser publicada com aviso **estrutural, não
   verificado em jogo**.
2. **Ponteiros repetidos com registros não explicados entre nomes:** nenhuma
   promoção. A perícia informa `dados_apos_marcador` ou
   `ponteiro_intercalado`, preservando registros em quarentena.
3. **Mais de dois aliases, ou dados inconsistentes para o mesmo ponteiro:**
   nenhuma promoção. Motivos `aliases_excessivos` e
   `aliases_inconsistentes`.

Os nomes continuam vinculados aos **índices da tabela**, não à ordem física
dos textos. O sistema não extrai nomes de outro mod e não edita a ISO. A
contagem de fronteiras é baseada nos registros físicos distintos (36 a 38),
sem declarar falsamente 38 fronteiras caso existam aliases.

A hipótese estrutural não desbloqueia nenhum drop, rótulo POW/TEC, RANK,
fusão ou efeito. O mapeamento de IDs precisa de observações independentes
em duelo real para ser considerado confirmado.

## Diagnóstico registrado

A seção `independent_opponent_discovery.forensicEvidence.windows` apresenta
`pointerAliasCount`, `pointerAliasGroups`, `maxAliasMultiplicity`,
`pointerNonIncreasingPairs`, `boundaryDecision` e contagens de registros.
A seção `boundaryTerminatorEvidence` apresenta candidatos que passaram
pelos critérios; os nomes privados não entram no resumo nem na IA local.

Ollama/Qwen permanece **opcional**, recebe apenas códigos e contagens; a
lógica determinística do scanner sempre decide o que é elegível.

## Testes

`tests/test_dueltrace_opponent_aliases.py` cobre:
- um e dois aliases em pools fisicamente compactados;
- preservação dos IDs originais mesmo com ponteiros invertidos;
- três aliases rejeitados mesmo quando o pool é consistente;
- duplicação artificial sem compactação, rejeitada pelos dados não nulos;
- ausência de nomes de candidatos e bytes proprietários no resumo;
- proteção contra liberação indevida de drops e RANK.

Os testes são **sintéticos**. Não foi disponibilizado o `relatorio.json` da
ISO GOG real, então ainda não há confirmação de reconhecimento dos 39
adversários nesta instalação.

## Próximo teste no Windows

1. Instalar Preview cujo build passou na CI e contém revisão 23.
2. Clicar **Atualizar dados** no GOG MOD 2.2 para reexaminar a ISO local.
3. Se aparecerem **39 adversários**, conferir a procedência estrutural e
   validar nomes/IDs observados no jogo.
4. Se a contagem continuar zerada, localizar a análise recente em
   `%LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\analises` e compartilhar
   `relatorio.json` (após revisar caminhos privados), especialmente os
   campos acima. Não enviar ISO, SLUS, saves nem Memory Cards.

**Ordem das próximas entregas:** correspondência de IDs observados em jogo,
leitura das referências MIPS para os 117 bancos de drops, validação dos
grupos/rótulos POW/TEC por ISO, e finalmente as fusões do próprio mod.
