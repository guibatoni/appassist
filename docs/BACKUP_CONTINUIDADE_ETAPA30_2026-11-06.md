# DUELTRACE — BACKUP DE CONTINUIDADE ETAPA 30 (06/11/2026)

## Base e privacidade
- Repo `guibatoni/appassist` privado; branch `feature/dueltrace-v097-real-iso-evidence-v30`, criada a partir da HEAD validada da Etapa29 `e9334c436d308711a148a4e404dd3e58aa99e643` (PR #77).
- Não fazer merge em `main`, não alterar Biblioteca 722/722, artes, leitor de mão, RANK, drops verificados nem integração remota opt-in.
- ISOs foram analisadas no ambiente local, **não** são adicionadas ao GitHub. Relatórios privados só devem conter metadados/contagens.

## Imagens e hashes

- Rising `RISING OF WICKED GODS 1.3.5 ver 2 - Drop 15 (NDC).bin`: SHA-256 `06b3a87fe7c29b0565b053718f9308212efbc9f7b9c20b1b7f7bcfc425f71b63`.
- Enhance `ENHANCE EDITION FINAL4 (Drop x15)(NDC).iso`: SHA-256 `6a1a897db35c5cf69ed631deba9793882ab2d6e9d71cf57d577267786bc10150`.
- Controle positivo Galaxy of Gods NT 2025: SHA-256 `8954b9d603270200bcf5c3edf404d5d18c772c4fb058bc017916f7c73c059d15`.
- Os 3 discos são ISO9660/2352 bytes/setor e têm `WA_MRG.MRG`, carregam 722 nomes FF com 722 IDs distintos.
- Rising/Enhance têm 39 adversários `FD u16 FF`, Rising field base 0x19A8 em 39/39, Enhance 38/39 e um desvio +1 na 11ª entrada.
- Enhance PS-X EXE possui entrada ISO9660 menor em 560 bytes do que `0x800+payload` e bytes zero no fim físico do setor; usar validação existente de padding real.

## Fusões reais (dados estruturais)
- Galaxy 18.553 triplas, 7 bancos idênticos, nenhum conflito.
- Enhance 24.953 triplas, 7 bancos idênticos, nenhum conflito.
- Rising 5.555 triplas, 7 bancos idênticos, seis detecções representando **3 pares unordered discordantes**; 5.549 pares sem conflitos. Não atribuir um resultado verdadeiro aos conflitos nem liberar todo o banco.
- Offsets sete bancos históricos: `0xB87800,0xBFD000,0xC72800,0xCE8000,0xD5D800,0xDD3000,0xE48800`.

## Drops (dados estruturais)
- Rising endereço convencional `0xE9B000` é 0xFFFF filler para as 117 tabelas. **39 blocos completos** identificados em `0x2421800`, etapa `0x1800`, stride `0x5B4`, deck plain + 3 masked, 117 matrizes somando 2048; fora do raio antigo de ±128 KB. A sonda global do WA pode detectar e, se for janela única, revalidar a decodificação.
- Enhance contém 117 grupos simples válidos em `0xE9B000`, mas é uma janela de 39 dentro de **40 blocos completos** iniciando em `0xE99800`. Duas janelas de 39 são possíveis; sem rótulos de RANK ou mapeamento de ID.
- Controle Galaxy tem 39 blocos completos desde `0xE9B000` e 117 masked. Não promover regras de Rising/Enhance ao controle.

## Código Etapa30
- Correção do detector FD com regra 38+1 sob nome/pointer único, sem prova em jogo; testes 1+1 rejeitados.
- Ponte `dueltrace_full_resource_drop_bridge.py` seleciona somente descoberta global única de 39x4 com revalidação 117 pelo decoder. `scanner_multiiso` utiliza apenas se a busca local de ±128K falhar; marca janela ambígua quando houver 40 blocos.
- `extrator_fusoes` informa pares conflitantes sem descartar contagens de receitas boas. `dueltrace_intelligence` salva em quarentena sete espelhos idênticos com conflitos e impede `import_structural_fusions` nesses casos.
- Testes sintéticos offline em `tests/test_dueltrace_inline_fd_names.py`, `tests/test_dueltrace_full_resource_drop_bridge.py`, `tests/test_dueltrace_intelligence.py`.
- Referência técnica: `docs/DUELTRACE_PHASE30_REAL_ISO_EVIDENCE.md`. Resultados completos em relatório privado de etapa 30 no workspace `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/`.

## Pendências e limite de prova
- Submeter CI Python/TS/Windows da HEAD da etapa30; ainda não declarar Windows aprovado até conferir resultado.
- Validar exportação Galaxy positiva, Rising e Enhance no Windows com novas versões sem apagar perfis anteriores.
- Resolver slot→ID de adversário, RANK efetivo, recebimento de drops e fusões conflitantes por trilha MIPS / execução no ePSXe. Não inferir identidade a partir de candidateId=5 de logs antigos.
- Não enviar ISO/BIN ao GitHub, nem dados de RAM bruta ou artes, nem ativar automaticamente drops/ranks por semelhança.
