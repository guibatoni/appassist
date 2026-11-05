# DUELTRACE — Engenharia reversa multi-ISO/BIN

## Objetivo de produto

O jogador escolhe sua ISO/BIN e joga. O DUELTRACE descobre a estrutura
do mod e extrai automaticamente o que puder ser **comprovado**. É impossível
garantir 100% de extração de qualquer mod sem uma análise específica, mas
podemos tornar o reconhecimento progressivamente genérico e auditável.

Não alterar código, RAM, ISO nem exportar arquivos do usuário para a rede.
Tudo acontece localmente. Cache e perfil separados por SHA-256 da imagem.

## O que o app consome

| Subsistema | Evidência necessária | Bloqueio em caso de incerteza |
| --- | --- | --- |
| Cartas | IDs, nomes, tipo, atributo, ATK, DEF e descrições por offsets e limites | Não promover catálogos parciais |
| Artes | TIM/formatos PS1, paletas, molduras e correspondência por ID | Não inventar imagens |
| Fusões | Rotina e/ou tabelas MIPS e regras verificadas no mod | Candidatas isoladas para revisão |
| Oponentes | IDs e nomes dos 39 ou outro layout comprovado | Não emprestar nomes do X15 |
| Drops | Pesos, bancos, oponentes, IDs e relação com sistema RANK | Peso coerente sem identidade continua candidato |
| RANK | Fórmula SPOILS, labels por ISO e leitura RAM vinculada ao processo real | Estimativa/experimento não vira resultado oficial |
| Efeitos | Texto declarativo, semântica executável e provas da rotina | Texto não comprova execução no jogo |

## Etapa 1 — leitor robusto da mídia (implementado no código)

- `scanner/dueltrace_cdrom_layout.py` distingue, pelo PVD ISO9660 validado,
  mídias 2048, 2352 Mode1/Mode2, 2336 Mode2 e 2448 com subcanal.
- Não escolhe geometria pela extensão nem apenas pelo tamanho, preservando
  o layout físico ao registrar `formato_fisico`.
- O leitor ISO9660 aplica limites de árvore, contagem, caminho, diretórios,
  extents e ciclos; fecha os arquivos mesmo quando o índice é inválido.
- `SCAN_PARSER_REVISION=8` força reapuração do cache antigo quando necessário.
- Testes sintéticos: todos os formatos, formatos renomeados, truncamentos,
  diretórios cíclicos, tamanho anormal e arquivo fora da mídia.
- Não garante suporte a imagens CUE/BIN com múltiplas trilhas, subQ danificado
  ou dumps sem ISO9660: estes casos devem ter diagnóstico específico.

## Etapa 2 — descoberta estrutural (próxima)

1. Fazer inventário de cada arquivo ISO9660 por extensão, tamanho, cabeçalho,
   entropia por amostra, assinaturas PS-X EXE/TIM/contêiner e BOOT do SYSTEM.CNF.
2. Ler executáveis PS-X EXE pelo cabeçalho e mapeamento RAM; mapear ponteiros
   usados no código MIPS sem assumir offsets do SLUS_014.11.
3. Encontrar tabelas candidatas de cartas, oponentes, fusões e drops por
   validação cruzada: limites, pesos, cardinalidade e referências.
4. Reportar, por estrutura, estado `confirmado`, `candidato` ou
   `indisponível`. A UI pública só mostra dados utilizáveis e textos simples.

## Etapa 2A — sondagem de nomes realocados (implementada como diagnóstico)

- `scanner/dueltrace_card_opponent_discovery.py` examina, em no máximo
  ±32 KiB da tabela de ponteiros de referência, candidatos a uma tabela
  conjunta de 722 cartas e 39 oponentes em executáveis de até 8 MiB.
- A busca usa glifos e a base de texto do layout conhecido; valida registros
  terminados por 0xFF, diversidade de nomes, amostras de IDs extremos e
  limites físicos entre nomes. Os offsets não são copiados de outras ISOs.
- O relatório interno `name_pointer_discovery` inclui deslocamento,
  contagens e amostras somente quando o decoder atual falha. Não popula
  o catálogo público, nem habilita drops/fusões/RANK a partir de hipóteses.
- Duas tabelas plausíveis continuam ambíguas. Glifos ou textos relocados,
  terminadores diferentes e layouts totalmente novos ainda não são
  identificados nesta etapa.
- `SCAN_PARSER_REVISION=9` faz o cache ser reavaliado.
- Testes sintéticos contemplam uma tabela relocada, ambiguidade, um nome
  truncado, orçamento de busca e ausência de glifos. Para promover dados à
  biblioteca será exigida evidência independente de identidade dos IDs.

## Etapa 3 — parser de mod sem layout conhecido

- Inferir deslocamentos com referências cruzadas MIPS, estrutura de ponteiros,
  sentinelas, strings e comparação diferencial entre versões do mod.
- Ferramentas gratuitas: **Ghidra** (decompilação e scripts/headless) para
  investigar; **Capstone** (disassembly MIPS integrado, após revisão técnica)
  para extrair pistas determinísticas. Nenhuma disassembly prova o efeito de
  um campo sem evidências adicionais.
- Confirmar cada estrutura com fontes independentes e testes de regressão
  contra Original, Remaster X15, FM13 e GOG MOD 2.2.
- Não fixar automaticamente a fórmula do X15 em outra imagem.

## IA gratuita opcional

- O DUELTRACE já possui Ollama local. Preferir reutilizar a infraestrutura
  antes de incorporar outro serviço, especialmente qualquer opção em nuvem.
- Modelo recomendado para **interpretar relatórios/símbolos MIPS**, não para
  interpretar bytes diretamente: `qwen2.5-coder:7b` (4,7 GB de pesos) ou
  `qwen2.5-coder:3b` (1,9 GB); ambos são opcionais e sujeitos ao desempenho.
- Para um PC de 16 GB RAM/8 GB VRAM, testar primeiro 3B e depois 7B. O usuário
  não deve ter que instalar IA para usar o app em mods já reconhecidos.
- Nunca enviar ROM/WA/SLUS/PNG completos ao modelo, nem salvar uma resposta de
  IA como offset, ID ou efeito confirmado. A IA apenas propõe investigações e
  fornece justificativas textuais para validação pelo parser.
- O Ghidra é uma ferramenta de desenvolvimento, não uma dependência obrigatória
  para os jogadores.

## Etapa 4 — automação completa e CI

- Importar ISO -> hash -> índice -> descoberta -> parser -> validação ->
  perfil por SHA -> ativação automática do que for confirmado.
- Reanalisar ao mudar parser/hash sem sobrescrever revisões humanas
  aprovadas nem perder arquivos do usuário.
- Testes unitários com imagens sintéticas; testes de integração com mods
  legalmente fornecidos; CI Windows e proteção de ZIP/release.
- Registrar claramente que validação em emulador real só é confirmada
  após executar o duelo correspondente. Não declarar suporte universal.

## Proteção contra perda de trabalho

Fonte atual: branch `feature/dueltrace-v097-opponent-validation`.
Começar cada nova etapa verificando HEAD, perfil, testes e diffs, então
commit incremental. Não reescrever módulos calibrados nem remover as
verificações de SHA/LP/RANK. Atualizar este documento por etapa.
