# DUELTRACE — Etapa 30: evidência direta de Rising e Enhance

Em 06/11/2026, o usuário forneceu **RISING OF WICKED GODS 1.3.5 ver 2 Drop 15 (NDC).bin** e **ENHANCE EDITION FINAL4 (Drop x15)(NDC).iso**. Foram examinadas localmente em modo somente leitura junto à referência funcional **FM Galaxy Of Gods NT Mod 2025**. **NENHUM arquivo ISO/BIN, arte, tabela de receitas ou dump bruto foi commitado**.

## SHA-256 das imagens examinadas

- Rising: `06b3a87fe7c29b0565b053718f9308212efbc9f7b9c20b1b7f7bcfc425f71b63`
- Enhance: `6a1a897db35c5cf69ed631deba9793882ab2d6e9d71cf57d577267786bc10150`
- Galaxy (controle positivo): `8954b9d603270200bcf5c3edf404d5d18c772c4fb058bc017916f7c73c059d15`

Todos possuem ISO9660 com setores físicos de 2352 bytes. Rising e Enhance possuem 9 arquivos; Galaxy 11. Rising e Enhance inicializam `SLUS_014.11`; Galaxy inicializa `GOG80925.NT` (há um segundo executável `SLUS_014.111`). Enhance declara PS-X EXE payload `0x1D0000`, embora o diretório liste 560 bytes a menos do que 0x800 + payload; o setor contém zeros de preenchimento verificáveis. A reparação segura já é possível pela rotina existente de sector padding, sem inventar bytes.

## Cartas e adversários

As três ISOs apresentam **722 nomes de cartas distintos, com FF**, e atributos compactos legíveis.

- Galaxy: 39 nomes de adversários com FF convencional.
- Rising: 39 ponteiros únicos para nomes com marcador `FD + u16 + FF`, e para todos os 39 o campo menos o comprimento codificado resulta em `0x19A8`.
- Enhance: os mesmos 39 ponteiros e marcadores; **38/39 campos base `0x19A8` e um `0x19A9` (11º registro)**. O detector antigo rejeita todo o conjunto porque exige 39 bases iguais. Etapa 30 aceita somente 38 iguais mais um **+1**, com 39 nomes e ponteiros distintos, um único conjunto de 39 e sem alegar IDs verificados em jogo. Dois desvios ou outras bases divergentes continuam rejeitados.

## Fusões decodificadas de sete bancos históricos

Offsets WA: `0xB87800, 0xBFD000, 0xC72800, 0xCE8000, 0xD5D800, 0xDD3000, 0xE48800`; cada banco possui 65536 bytes. Os sete espelhos são equivalentes **dentro de cada ISO**, com algoritmos do scanner existente:

| ISO | Triplas de fusão distintas | Detecções de conflito | Pares não ordenados ambíguos |
|---|---:|---:|---:|
| Galaxy | 18.553 | 0 | 0 |
| Rising | **5.555** | 6 | **3** |
| Enhance | **24.953** | 0 | 0 |

Rising tem **5.549 pares não ordenados sem conflito**, três pares com resultados duplos, e seis detecções do verificador por reciprocidade. Etapa30 agora **mantém o relatório local de sete bancos com conflitos em quarentena**; não habilita nenhuma fusão desse conjunto por inferência. Enhance pode seguir os testes normais de sete bancos idênticos, mas execução em jogo permanece por validar.

## Drops e tabelas 39x4

- Galaxy (controle): 39 blocos completos de 0x1800 em `WA_MRG.MRG:0xE9B000`, 117 grupos de drops mascarados validados pela soma 2048.
- Rising: **no endereço legado 0xE9B000 há preenchimento 0xFFFF, não tabelas**. O scanner local encontrou 39 blocos completos de 0x1800 em **`0x2421800`**, stride 0x5B4: deck direto + três distribuições mascaradas por bloco, 117/117 com soma normalizada 2048. A busca antiga de realocação estava limitada a ±128 KiB do endereço original, portanto não alcançava essa região. Etapa30 aproveita a **sonda global 156 matrizes** já existente, mas somente quando há **uma janela única** e o decoder independente confirma novamente as 117 tabelas. IDs e grupos RANK continuam não verificados.
- Enhance: 117/117 matrizes diretas no endereço legado `0xE9B000`, mas a varredura encontra uma sequência de **40 blocos físicos completos desde `0xE99800`**. Tanto `0xE99800` quanto `0xE9B000` iniciam janelas completas de 39: é impossível vincular grupos ao nome do adversário só pela soma dos pesos. Etapa30 marca a ambiguidade para não liberar associação nem RANK.

## Arquivos alterados

- `scanner/dueltrace_inline_fd_names.py`: tolerância estrita à exceção 38+1, ainda estrutural.
- `scanner/dueltrace_full_resource_drop_bridge.py`: candidato do recurso completo com 156 matrizes, revalidado e sem promoção.
- `scanner/scanner_multiiso.py`: fallback para distância grande e bloqueio de janela 40→39 ambígua.
- `scanner/extrator_fusoes.py`: resumo de pares de fusão sem conflito e pares não ordenados ambíguos.
- `scanner/dueltrace_intelligence.py`: mantém dados de sete bancos com conflitos em quarentena e evita importação automática.
- Testes sintéticos sem binários comerciais: `tests/test_dueltrace_inline_fd_names.py`, `tests/test_dueltrace_full_resource_drop_bridge.py`, `tests/test_dueltrace_intelligence.py`.

## Gatilhos ausentes

A extração estrutural **não prova** execução de fusões, ID de oponente em RAM, início/fim de duelo, associação posição→nome, rótulos Z/S/TEC, drops efetivamente recebidos ou efeitos de cartas. Esses pontos requerem trace MIPS e observação independente do ePSXe. Conservar todas as funções já corretas do controle Galaxy. **Sem merge na main** e sem publicação automática de imagens ou dados privados.
