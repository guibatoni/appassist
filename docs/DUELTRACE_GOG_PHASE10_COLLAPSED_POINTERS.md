# DUELTRACE — Etapa 10: falso positivo de 39 adversários por 1 ponteiro

## Evidência real fornecida pelo usuário

O diagnóstico copiado do próprio `GOG MOD 2.2 - Drop 15 (NDC).iso`
na revisão 23 mostra, nas cinco janelas:

- `candidateReadable=39`, `terminatedFF=39`;
- `pointerCountDistinct=1`;
- `pointerAliasCount=38`, `pointerAliasGroups=1`, `maxAliasMultiplicity=39`;
- `pointerSpanMin=0`, `pointerSpanMax=0`;
- `recordBoundaryKnown=39`, **`recordBoundaryReached=0`**;
- `recordWithHeader=0`;
- `boundaryDecision=aliases_excessivos`.

**Conclusão sustentada:** são 39 leituras do mesmo endereço, não 39
strings de adversários independentes. O byte `0xFF` é a repetição do
terminador de uma mesma string. Isso indica que a região de ponteiros
interpretada pode ser um placeholder, uma tabela incompatível ou uma
base incorreta. **O valor real do ponteiro e a localização da tabela
verdadeira ainda não foram comprovados.**

Não aumentar o limite de aliases para 38/39. Isso apenas promoveria
39 entradas duplicadas falsas.

## Implementado — parser revisão 24

1. O leitor de tabelas independentes mantém separadas janelas com
   menos de 24 ponteiros OU prefixos legíveis distintos (limiar
   exploratório, não validação de IDs). Elas são **descartadas como
   candidatos a adversários** e preservadas somente como evidência.
2. `candidateOpponentCount` mede a quantidade mínima coerente de
   endereços, nomes distintos e nomes legíveis; não usa o total bruto
   de leituras repetidas.
3. `degenerateEvidence` informa quantidade de janelas rejeitadas,
   ponteiros distintos na melhor janela, registros repetidos e se
   todos os ponteiros eram zero — sem publicar nomes ou offsets.
4. `forensicEvidence` continua registrando a janela degenerada
   mesmo com **0 candidatos independentes**. O botão **Copiar
   diagnóstico técnico** segue disponível.
5. A interface mostra: **Nenhuma sequência independente de adversários
   encontrada nesta região**, com motivo específico de um só ponteiro,
   em vez da falsa afirmação "até 39 nomes candidatos".
6. O scanner remove arquivos de quarentena gerados em varreduras
   anteriores quando reanalisa a mesma ISO.
7. A revisão 24 invalida o cache anterior para nova análise no Windows.

## Buscas alternativas já existentes

O `scanner_multiiso.py` já executa, quando não encontra adversários:

- `discover_relocated_name_table`, a busca por outra tabela de ponteiros;
- `discover_relocated_name_layout`, para bases deslocadas de
  ponteiros/textos/glifos;
- `inspect_mips_table_references`, que reúne referências estáticas
  MIPS para candidatos.

A API `get_mod_scan_diagnostic` e o JSON sanitizado copiado agora
incluem `alternativeLayoutSearch` com **somente contagens e estados
permitidos** das três sondas. Isso permite identificar onde aprofundar
sem publicar endereços RAM, nomes, conteúdo do executável ou caminhos
locais. Uma referência MIPS candidata NÃO prova execução.

## O que ainda não sabemos

- Se os ponteiros repetidos são zero ou outro endereço constante.
- Onde começa a tabela real dos 39 adversários do GOG MOD 2.2.
- Se há 39 nomes genuinamente separados e qual ordem de IDs o jogo usa.
- Quais das 117 matrizes correspondem a cada adversário e grupo de
  drops POW/TEC.
- Onde estão as regras de fusão da própria ISO e como se vinculam
  aos IDs de cartas.

## Como continuar com dados reais

1. Instalar a Preview Windows desta revisão **apenas após CI aprovada**.
2. Na Biblioteca de Mods, clicar **Atualizar dados** no GOG MOD 2.2.
3. Confirmar que os 39 duplicados **não aparecem mais como 39 nomes candidatos**.
4. Usar **Copiar diagnóstico técnico** e compartilhar o novo JSON,
   especialmente `forensicWindows` e `alternativeLayoutSearch`.
5. Se a busca alternativa também retornar zero, usar
   `relatorio.json` da análise local para inspecionar os candidatos
   MIPS, glifos e possíveis bases sem elevar heurísticas arbitrárias.
6. Validar IDs de adversários em duelo real antes de desbloquear drops
   ou rótulos RANK.

Os testes são sintéticos; não temos a ISO GOG real neste ambiente.
O código fica em uma PR separada e **não é mesclado automaticamente
à main**. As 722 cartas estruturalmente extraídas permanecem
preservadas, mas seus IDs ainda não foram confirmados em jogo.

## Segurança e privacidade

Não compartilhar ROM, executável comercial, Memory Card, saves,
caminhos pessoais ou hashes completos. O diagnóstico copiado é uma
lista restrita de contadores, classificações e estados. Nenhuma IA
local ou em nuvem pode promover dados sem validação binária.
