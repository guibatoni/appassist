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

## Etapa 2B — Capstone + evidência cruzada com MIPS (implementada)

- `scanner/dueltrace_mips_reference_probe.py` procura pares estruturais
  `LUI` + `ORI/ADDIU` ou instruções de carga MIPS que referenciem
  os primeiros 32 bytes de tabelas candidatas.
- O endereço é transformado usando somente o cabeçalho PS-X EXE do mesmo
  arquivo, com aliases de RAM KSEG0/KSEG1. A janela de análise fica limitada
  a 2 MiB e até 16 referências. Não emula nem executa código.
- Capstone está fixado em `5.0.9` para o build Windows; se indisponível, o
  reconhecedor estrutural continua funcionando. A desmontagem Capstone
  enriquece o relatório, **não** aumenta a confiança automaticamente.
- Os resultados `mips_name_pointer_evidence` ficam no relatório interno e
  chegam ao Ollama apenas como metadados compactos, com SHA-256 do exe.
  O usuário final não vê offsets ou avisos experimentais.
- `validated=false`, `executionConfirmed=false` em toda referência.
  Mesmo um PC encontrado não comprova que o jogo realmente acessa aquela
  tabela ou que os IDs correspondem aos textos apresentados.

### Ghidra opcional para desenvolvimento

- Exportador `tools/reverse_engineering/DueltraceXrefs.java`: script de
  **Ghidra Headless** que coleta referências estáticas a endereços selecionados.
- Rodar apenas pelo desenvolvedor, com Ghidra instalado separadamente,
  executável importado com mapeamento MIPS correto e projeto temporário.
  Exemplo conceitual da CLI, a adaptar ao diretório local:

  ```powershell
  & "C:\Ghidra\support\analyzeHeadless.bat" "C:\DUELTRACE-Work" "Analisador" -import "C:\mods\GAME.EXE" -scriptPath "C:\appassist\tools\reverse_engineering" -postScript DueltraceXrefs.java "C:\DUELTRACE-Work\evidencias.json" 80012000 -readOnly
  ```

- A importação correta do PS-X EXE e os endereços carregados pelo Ghidra
  precisam ser conferidos antes de interpretar o relatório.
- O executável Ghidra **não é enviado** junto com o DUELTRACE e não é iniciado
  automaticamente, evitando downloads, Java e custo de manutenção para
  o jogador. Os resultados Ghidra são pistas e nunca promovidos a perfil.

### IA local

- Ollama e `qwen2.5:3b` já fazem parte do fluxo de investigação opcional.
  Não instala, baixa nem executa automaticamente outro modelo.
- A IA só recebe resumos e evidências; não recebe ISO, ROM, SLUS ou arquivos
  de memória completos, não edita offsets e não aprova catálogos/drops/RANK.

## Etapa 2C — identificação conjunta de textos e glifos (candidatos)

- `scanner/dueltrace_relocated_names.py` pesquisa tabelas de ponteiros u16
  próximas ao offset de referência; identifica bases de texto usando
  cabeçalhos `F8 0A` distribuídos em registros de cartas e oponentes,
  e procura glifos Shift-JIS em células de 4 bytes.
- A sondagem considera até ±32 KiB para ponteiros/textos e ±16 KiB para
  glifos, 6 candidatos de ponteiros, 8 de textos/glifos e 6 combinações
  finais; são limites de desempenho, não uma garantia de compatibilidade.
- Cada combinação exige registros `FF` completos para os IDs extremos,
  no mínimo 720/722 cartas, 38/39 oponentes e diversidade de nomes.
  Nenhum candidato é ativado na Biblioteca.
- Há risco de falso positivo mesmo com as evidências. Dois layouts válidos
  permanecem `hipoteses_ambiguas`; no catálogo público a resposta continua
  como indisponível até prova independente da identidade.
- O relatório `relocated_name_layouts` guarda deslocamentos, amostras
  e contagens para desenvolvedores; as referências MIPS analisam também
  as novas bases encontradas.
- Ollama recebe apenas resumos compactos não verificados, sem os bytes
  do executável, e não pode promover qualquer hipótese a fonte oficial.
- `SCAN_PARSER_REVISION=11` invalida resultados de cache antigo.
- Ainda não cobre mods com outro terminador, formato sem F8 0A,
  compressão, texto com ponteiros 32-bit, glifos sem célula Shift-JIS,
  tabelas com nomes fora de ordem ou alterações de cardinalidade.

## Etapa 2D — vínculo de nomes, IDs e atributos (somente evidências)

- `scanner/dueltrace_card_attribute_probe.py` investiga as duas tabelas
  conhecidas do layout FM dentro do mesmo executável: 722 palavras de
  quatro bytes (ATK/DEF/tipo/estrelas) e 722 bytes (nível/atributo).
- Cada tabela pode ser deslocada independentemente até ±16 KiB. A análise
  exige limites do arquivo, amostras distribuídas, variedade real de
  estatísticas e categorias, além de coerência dos registros completos.
- **Não** procurar por tamanho ou cabeçalho apenas: o scanner só cruza
  atributos com layouts de nomes identificados *no mesmo executável*,
  redecodificando 722 cartas e 39 oponentes antes de vincular os IDs.
- Deslocamentos adjacentes podem produzir registros parecidos. O algoritmo
  verifica os extremos e favorece fronteiras plausíveis, mas **não**
  considera esse indício confirmação da posição correta.
- Relatórios `card_attribute_layouts` e `mips_card_attribute_evidence`
  contêm base das tabelas, deslocamentos, 5 amostras de cartas e referências
  estáticas à RAM. Só chegam a diagnósticos internos e a um resumo compacto
  para Ollama; não alteram o perfil público, os drops ou a calculadora.
- `validated=false` e `inGameVerified=false` persistem até
  confirmação independente com uma ISO real e o jogo no emulador.
- `SCAN_PARSER_REVISION=12` invalida o cache do scanner para reanálise.
- Testes sintéticos cobrem deslocamento conjunto/independente, duplicação,
  registros ausentes, intervalos e correspondência do hash do executável.
- Os limiares correspondem ao **layout clássico** com ATK/DEF em dezenas
  e distribuição típica de valores. Mods que alterem a codificação,
  removam cartas ou mudem a cardinalidade exigirão adaptadores novos.
  Rejeição do layout não prova ausência de cartas nem de atributos.

## Etapa 2E — importação parcial e seleção segura de recursos (implementada)

- O scanner não exige mais WA para aproveitar nomes, atributos e oponentes
  extraídos de um executável válido. Ausência de WA deixa drops, artes e
  tabelas de pontos indisponíveis, sem abortar a análise completa.
- Também preserva inventário, SYSTEM.CNF, assinaturas, cabeçalhos e relatório
  quando não existe um executável compatível.
- `scanner/dueltrace_resource_selection.py` sonda **até 6 contêineres de
  96 MiB**, identificados por nome, tamanho ou matrizes estruturais.
- Cada candidato precisa ser lido por completo, com SHA-256, e testado
  com as 117 matrizes de pesos. Um único resultado estrutural permite
  selecionar o *arquivo*, mas não comprova os IDs de cartas, oponentes ou
  etiquetas de RANK. Isso só ocorre na validação específica do perfil.
- Duas alternativas estruturalmente consistentes com SHA diferente
  continuam **ambíguas**. Cópias idênticas são equivalentes.
  Contêineres com leitura truncada ou alterações entre duas leituras
  são rejeitados, sem reutilizar conteúdo de varredura anterior.
- Se nenhum contêiner tiver layout conhecido, somente uma alternativa
  isolada ou um nome convencional único pode ser mantido para investigação
  de outras estruturas; dados de drops permanecem indisponíveis.
- Memória máxima simultânea evita armazenar seis arquivos inteiros:
  o scanner mantém só digests e metadados até reler o vencedor.
- `SCAN_PARSER_REVISION=13` reavalia caches criados por leitores antigos.
- Testes cobrem WA ausente com cartas presentes, inventário sem EXE,
  múltiplos candidatos válidos, cópias iguais, conteúdo truncado e
  arquivo alterado durante a leitura.
- **Importante:** reconhecer uma ISO parcialmente não significa que
  todas as funcionalidades funcionem para aquele mod. Falhas de parsing
  são preservadas como diagnóstico, sem criar dados de outros mods.

## Etapa 2F — modo básico para mods sem catálogo

- ISOs com índice de disco legível e análise parcial podem ser ativadas
  **mediante confirmação do jogador** mesmo sem 722 cartas reconhecidas.
- A ativação estabelece `compatibility_mode=basic`; mantém somente
  IDs e LP condicionados a uma leitura RAM real, e bloqueia nomes, artes,
  drops, RANK, pontuação e fusões inexistentes.
- ISOs corrompidas ou com `scanner_error` não podem usar o modo básico.
  Mesmo nos demais casos, iniciar o jogo depende do ePSXe instalado,
  arquivo original intacto e confirmação do usuário na interface.
- O botão para ativar usa o texto simples `Modo básico` quando necessário.
  O app não afirma que o mod é totalmente compatível nem que uma sessão
  do ePSXe corresponde automaticamente à ISO ativa no DUELTRACE.
- Testes verificam ausência de vazamentos de dados entre ISOs e comando
  de inicialização do ePSXe limitado ao arquivo ativo.

## Etapa 2G — descoberta de 117 matrizes de drops em contêiner realocado

- `scanner/dueltrace_drop_layout_discovery.py` procura conjuntos de
  39 duelistas × 3 grupos × 722 pesos dentro de um WA renomeado ou deslocado.
  Usa limites de ±128 KiB da base conhecida, alinhamento progressivo e
  candidatos limitados de stride de oponente e distância entre grupos.
- Não basta uma tabela com soma 2048: a validação exige **117 matrizes**
  completas, cada uma com codificação simples ou mascarada consistente.
  Registros corrompidos ou dois layouts plausíveis não são ativados.
- `decode_drops` recebeu parâmetros de base, stride e distância, para
  extrair offsets de origem reais quando um layout candidato é único.
- Em layout novo, os grupos recebem nomes genéricos
  `GRUPO_1`, `GRUPO_2`, `GRUPO_3`; não afirmar que correspondam a
  S-POW, S-TEC ou Z-POW sem evidência independente.
- `scanner/dueltrace_resource_selection.py` pode reconhecer um arquivo
  arbitrário de recursos quando a estrutura deslocada é única. Se nome,
  assinatura e tamanho não ajudarem, investiga um conjunto limitado de
  grandes contêineres inventariados pelo índice ISO9660.
- Os critérios completos do importador continuam obrigatórios para
  associar drops a cartas e oponentes da ISO. Extração estrutural não
  demonstra qual RANK é mostrado pelo jogo.
- `SCAN_PARSER_REVISION=15` invalida caches anteriores.
- Testes sintéticos verificam base deslocada, stride alterado, pesos
  mascarados, 117 matrizes, corrupções, duas hipóteses e recursos
  arbitrariamente renomeados.
- **Limitação:** não cobre todas as compressões, hashes, criptografias,
  cardinalidades alteradas ou formatos sem tabela de 16 bits. Futuras
  famílias precisam de novos adaptadores e evidência real do mod.

## Etapa 2H — matriz automática para testar coleções de mods

- `scanner/dueltrace_compatibility_matrix.py` gera um JSON **local**
  por SHA-256, com cobertura de cartas, oponentes, drops, fusões, artes,
  descrições, efeitos e RANK, mais estados das sondagens ainda incertas.
- Nunca exporta bytes de ROM/ISO, caminhos originais, dados RAM, nomes de
  usuários ou as tabelas completas. Não chama Ollama nem envia dados à rede.
- Pode analisar uma pasta inteira reaproveitando o cache do Catálogo:

  ```powershell
  python scanner/dueltrace_compatibility_matrix.py --folder "D:\MeusMods" --output "D:\Relatorios\compatibilidade.json"
  ```

- Também funciona sobre mods já importados, com `--home` apontando ao
  diretório local de dados do DUELTRACE e sem `--folder`.
- Níveis de compatibilidade não significam validação em duelo: o campo
  `inGameValidationClaimed=false` permanece explícito. Só dados com SHA
  correspondente entram no resumo.
- Esse relatório é a entrada recomendada para comparar Original, X15,
  GOG MOD 2.2, FM13 e variações legais fornecidas pelos usuários.
- Mantenha tabelas originais de jogadores e dados de ROM fora do GitHub,
  compartilhando apenas o JSON quando desejar revisar compatibilidade.
- Em tabelas degeneradas com peso 2048 em uma única carta, múltiplos
  alinhamentos de bytes podem parecer válidos. O parser **mantém ambiguidade**
  em vez de assumir o primeiro offset encontrado.

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
