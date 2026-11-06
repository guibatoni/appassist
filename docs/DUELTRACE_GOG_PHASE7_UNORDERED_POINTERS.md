# DUELTRACE — Etapa 7: índices de adversários fora de ordem física (GOG MOD 2.2)

## Evidência observada

A imagem `GOG MOD 2.2 - Drop 15 (NDC).iso` continua exibindo **722 cartas**, e o scanner informa até **39 adversários candidatos**, mas nenhum adversário publicado. O diagnóstico da revisão 21 é:

> Os ponteiros são repetidos ou não seguem ordem física crescente. Evidência preservada para engenharia reversa.

Esse aviso agrupava duas situações **diferentes**:
1. Ponteiros **únicos, mas fora de ordem** no vetor de IDs — podem ser estruturalmente legítimos.
2. Ponteiros **duplicados** (aliases) — podem representar compartilhamento, lacunas ou outro formato; não comprovam 39 IDs distintos.

Não temos o `relatorio.json` real do GOG e não é correto afirmar qual situação ocorreu apenas pela imagem.

## Correção na revisão 22

`scanner/dueltrace_opponent_boundary_probe.py` agora preserva a relação
`ID da tabela -> ponteiro de texto` e valida nomes em **ordem física**
independentemente da ordem ordinal dos IDs.

- Exige 39 ponteiros únicos dentro do executável. **Ponteiros repetidos continuam bloqueados**.
- Ordena *uma cópia* dos 39 ponteiros por endereço físico para confirmar as 38 fronteiras entre registros.
- Mantém cada nome conectado a seu índice original. **Não renumera IDs segundo a posição dos bytes**.
- Rejeita sobreposições entre marcador de fim e próximo registro, ponteiros intercalados de outras tabelas, bytes não nulos após delimitador e cabeçalhos inválidos.
- A regra anterior de terminador alternativo, diversidade de nomes e ausência de blocos concorrentes permanece obrigatória.
- A eventual aceitação é **exclusivamente estrutural**: não comprova que o jogo use a mesma ordem durante duelos.
- A análise forense registra `pointerAliasCount`, `pointerNonIncreasingPairs`, `physicalOrderRemapped`, `boundaryDecision` e motivo de recusa para cada janela.
- `SCAN_PARSER_REVISION=22`: força reanálise ao clicar **Atualizar dados**.

### Tratamento de aliases

Se dois IDs apontarem para o mesmo endereço, o sistema registra
`ponteiros_repetidos`, preserva os registros candidatos em quarentena e
não os atribui arbitrariamente a adversários, drops ou RANK. Futuramente
poderemos investigar aliases legítimos com referências de execução MIPS
e observações de nomes/IDs no emulador.

## Regressões

`tests/test_dueltrace_independent_opponents.py` contém casos sintéticos
que comprovam:
- dois primeiros ponteiros invertidos: sequência estrutural recuperada, com nomes ainda nos IDs originais;
- tabela inteira de 39 ponteiros em ordem inversa: 38 inversões, 38 fronteiras físicas reconhecidas;
- ponteiros repetidos: nomes não promovidos, código de recusa específico;
- proteção existente contra terminadores mistos, blocos concorrentes e drops/RANK não confirmados.

**Testes sintéticos não equivalem a validação no GOG real.**

## Próximo teste no Windows

1. Instalar somente uma Preview **aprovada na CI do commit final**.
2. Na Biblioteca de Mods, selecionar GOG e clicar **Atualizar dados**.
3. Se o total de adversários passar para 39, verificar o aviso de procedência: a identidade dos IDs segue pendente em jogo.
4. Se permanecer `—`, abrir o relatório real `relatorio.json` em
   `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\analises` e verificar:
   `independent_opponent_discovery.forensicEvidence.windows`,
   particularmente `pointerAliasCount`, `pointerNonIncreasingPairs` e
   `boundaryDecision`.
5. Revisar os caminhos particulares antes de compartilhar o relatório.
   Nunca adicionar a ISO, o executável proprietário ou Memory Card ao GitHub.

A ordem de trabalho após identificação estrutural: **IDs adversários em
duelo real → cruzamento dos 117 bancos de drops por referência MIPS →
rótulos POW/TEC por ISO → fusões próprias do mod**.

A IA Ollama permanece opcional. Ela interpreta diagnósticos numéricos,
não substitui disassembly nem autoriza promoção de dados.
