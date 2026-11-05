# DUELTRACE — Leitura independente de cartas (GOG MOD 2.2 e outros mods)

## Sintoma confirmado na interface

O card de um mod mostra "—" para cartas, fusões, oponentes e drops.
Isso significa que o **perfil de jogo não possui esses recursos liberados**;
não significa necessariamente que a ISO não contenha cartas.

O código antigo fazia duas operações acopladas: (a) `decode_names`
descartava todas as cartas quando menos de 30 nomes de oponentes eram
decodificados; e (b) `scanner_multiiso.process` só escrevia
`cartas.csv` quando `oponentes` estava preenchido.

## Correção conservadora — parser revisão 17

- A leitura de ponteiros de 722 cartas e de 39 adversários é independente.
  Ponteiros incorretos de adversários não encurtam registros válidos de cartas.
- Seleção de executável favorece um catálogo integral e aceita catálogo
  somente de cartas caso nenhum executável tenha ambos os grupos.
- Para admitir apenas as 722 cartas sem adversários, exigir:
  - os 722 nomes terminados por `FF`, plausíveis e com pelo menos 680 distintos;
  - tabela compactada de ATK/DEF/tipo e tabela de detalhes presentes nos
    offsets conhecidos do próprio executável, com métricas fortes de
    consistência e limites físicos;
  - nenhum empréstimo de dados entre ISOs.
- `cartas.csv` passa a ser escrito mesmo se `oponentes.csv` faltar.
- O importador libera a Biblioteca de cartas para um catálogo que passou
  nas validações estruturais, mas usa `cartas: extraidas_estruturalmente`
  no perfil quando os adversários não puderam ser identificados.
  **Esse estado NÃO equivale a validação em jogo.**
- Drops, rotulagem de bancos, RANK, fusões e artes não são habilitados
  automaticamente apenas por reconhecer cartas.
- O front-end deixa claro se um mod tem cartas estruturalmente extraídas,
  registros candidatos em quarentena ou nenhum catálogo reconhecido.
- `Atualizar dados` já usa reanálise forçada da ISO por SHA; nova revisão
  invalida caches antigos e o botão indica se a tentativa descobriu cartas.

## Limites explícitos

Sem o GOG MOD 2.2 real e seu `relatorio.json`, não há prova de que
seus nomes e atributos estão nos offsets clássicos. Mods que deslocam
tabelas, alteram terminadores, comprimem nomes ou remapeiam IDs continuam
exigindo investigação separada (sondagens MIPS e decodificadores novos).
O arquivo candidato em quarentena **não** é incorporado ao perfil como
se tivesse sido confirmado em duelo.

## Como testar no Windows

1. Utilize uma Preview baseada na revisão 17 **após confirmar o sucesso
   da CI e a publicação**. Não atribua uma release antiga a este commit.
2. Expanda o GOG MOD 2.2 na Biblioteca de Mods e clique **Atualizar dados**.
3. Observe separadamente Cartas, Oponentes, Fusões e Drops; confira
   o aviso de procedência sob as métricas.
4. Se Cartas continuar em 0, localize o relatório de análise mais
   recente em `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\analises\`
   (subpastas específicas da ISO). O arquivo `relatorio.json` é
   suficiente para identificar qual estágio falhou:
   `nomes_status`, `executavel`, `name_pointer_discovery`,
   `relocated_name_layouts`, `card_attribute_layouts` e
   `candidate_catalogue`.
5. Revise o relatório local antes de compartilhar, pois pode conter
   nomes e caminhos de arquivos. **Não envie ISO, saves, Memory Cards,
   tokens nem binários proprietários ao GitHub.**

## Testes de regressão

`tests/test_dueltrace_independent_cards.py` contém casos sintéticos
de 722 cartas com 39 adversários, de 722 cartas com adversários
inválidos, rejeição de atributos inválidos, preferência do executável
completo, perfil parcial sem drops nem RANK e revisão do cache.

Não prometemos suporte universal nem dados inventados. Cada mod deve ser
validado por seu próprio SHA-256 e evidências verificáveis.
