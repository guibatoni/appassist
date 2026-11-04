# Integridade dos catálogos e associação de drops

## Correção

A v0.9.6 promovia os drops no importador quando havia 722 cartas, 39 nomes
de oponentes e um CSV declarando 117 somas iguais a 2048. Essa declaração não
conferia se as linhas efetivas de drops continham as mesmas matrizes, IDs válidos
e somas corretas. A API de consulta já verificava os pesos, mas ainda podia
substituir uma referência sem carta por `Carta #ID`, ocultando um catálogo
incompleto. O novo importador verifica a coerência antes de disponibilizar dados.

- Todos os IDs de cartas 1–722 e oponentes 1–39 precisam aparecer exatamente
  uma vez, na ordem de extração. Nomes vazios, caracteres de controle e glifos de
  substituição são rejeitados. Nenhum sufixo é removido.
- ATK/DEF devem corresponder à codificação de nove bits multiplicados por dez;
  tipo, nível, atributo e estrelas precisam caber nos campos binários do layout.
  Esses limites verificam a estrutura, **não** comprovam a semântica de um mod
  que tenha redefinido os campos.
- As linhas efetivas de drops precisam reconstruir 39 × 3 matrizes distintas,
  cada uma com soma 2048, referências a IDs 1–722, pesos positivos e sem repetição
  de carta no mesmo grupo/oponente. As probabilidades são calculadas a partir do
  peso, sem confiar na coluna textual de porcentagem do CSV.
- A proveniência registra o SHA completo da ISO e o resultado da validação.
  O importador confere o SHA retornado pelo scanner com o hash da imagem e o
  relatório salvo. A consulta recusa proveniência explícita de outra ISO,
  IDs de carta ausentes e IDs duplicados. A API exige o catálogo completo de
  722 IDs e o estado de cartas verificado, mesmo se os drops referenciam apenas
  uma carta. Perfis antigos completos sem o novo campo de proveniência continuam
  aceitos quando passam nas verificações anteriores.

## Evidência preservada

Matrizes declaradas estruturalmente plausíveis continuam com seus contadores
provisórios e CSVs locais, mesmo se a associação falhar. Os erros são registrados
em `drops_provenance.association_validation`, e `supported_features.drops` fica
desativado. O catálogo de cartas/oponentes permanece disponível quando passa nas
suas próprias verificações; uma falha nas matrizes não apaga nomes válidos.

Não se reescreve ou promove um perfil antigo só porque o programa foi atualizado.
A nova validação de extração acontece na reanálise explícita da ISO.

## Testes e limites

`tests/test_dueltrace_catalog_validation.py` cobre catálogos completos, todos os
registros, atributos fora da codificação, IDs repetidos, pesos contraditórios,
grupos ausentes, duplicatas e SHA inválido. As regressões de importação verificam
a preservação de evidência provisória, a quarentena de associações inconsistentes
e probabilidades derivadas dos pesos. Os testes de consulta verificam referências
ausentes e troca de SHA.

Tudo usa dados sintéticos. Os 39 nomes, os atributos das 722 cartas e as 4.543
entradas provisórias do GOG MOD real continuam pendentes de comparação com a ISO
e o jogo. A estrutura coerente de 117 tabelas não comprova a ordem dos grupos de
RANK nem resultados observados em duelo. Nenhuma fórmula de Spoils/RANK é alterada.
