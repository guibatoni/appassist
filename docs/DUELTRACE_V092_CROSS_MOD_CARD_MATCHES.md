# DUELTRACE v0.9.2 — Identificador Universal de Cartas (primeira etapa)

**Origem:** v0.9.1, PR #41, HEAD `937c1a22ba6327d0ae8859a1f7155d73f16ebbf9`.
**Branch:** `feature/dueltrace-v092-cross-mod-card-matcher`.

## Objetivo

Comparar os catálogos de duas ISOs/BIN locais de Yu-Gi-Oh! Forbidden Memories mesmo quando cartas mudam de ID, atributos, nome ou arte. Garantir que nomes/IDs semelhantes **não provoquem transferências incorretas** entre mods. O usuário apresentou as cartas *Fungi of the Musk*, *Flower Wolf* e *Queen of Autumn Leaves* como referências visuais de diferenças entre mods.

## Mecanismo implementado

- **Scanner já existente** extrai do SLUS os nomes, atributos, tipos, níveis e demais dados do catálogo, e do WA_MRG as artes 102×96 PNG em layouts suportados. Os perfis são separados por SHA-256 da ISO.
- Novo `scanner/dueltrace_card_matcher.py`: compara **dois catálogos de cartas previamente extraídos e marcados como validados pelo parser**. Normaliza nomes, compara estatísticas e tipos, calcula SHA-256 dos **pixels RGB** das artes extraídas, e sinaliza possíveis equivalências entre IDs diferentes.
- As artes devem ser PNGs 102×96 dentro do diretório de análises local autorizado, limitados a 500 kB. Arte uniforme/placeholder e hashes repetidos não são evidência de identidade. Não se envia nem copia o PNG.
- **ID numérico igual NÃO é evidência.** Duas cartas no mesmo ID podem ser diferentes em cada mod. Nome duplicado é sinal de ambiguidade. Correspondências fortes exigem nome único + ATK/DEF coincidentes ou arte idêntica e única.
- As classes são `alta` (candidata forte), `revisar` (ambígua, dados divergentes ou nome similar) e `sem_correspondencia`. Nem mesmo `alta` significa identidade confirmada no jogo.
- Validação 1:1 evita marcar duas cartas de origem como correspondências fortes do mesmo ID destino. Nunca transfere automaticamente cartas, imagens, fusões, drops ou efeitos.
- Nova API do Windows `compare_mod_cards`: token local, compara apenas duas ISOs importadas no catálogo, cache por revisão dos perfis e paginação 30/40 cartas; não retorna caminhos, ISO, tokens nem metadados brutos do disco.
- Interface **Biblioteca de Mods → Identificador Universal de Cartas**: selecionar duas ISOs, comparar, pesquisar IDs e nomes, filtrar por confiança, paginar, contar IDs de origem diferentes dos IDs de destino.

## Ollama local (opcional)

- Novo `scanner/dueltrace_card_match_ai.py`: somente por clique explícito em **Revisar dúvidas com Ollama**. Usa o modelo local `qwen2.5:3b` e o endpoint `127.0.0.1:11434`, não envia dados para APIs externas.
- O modelo vê até 12 pares ambíguos **já encontrados pelo scanner**, apenas IDs, nomes e sinais normalizados. Não recebe arquivos SLUS, WA_MRG, PNGs, ISO ou Memory Card.
- JSON gerado é rigidamente validado: somente pares originais da lista podem aparecer. Pareceres: `manter_candidata`, `revisar`, `descartar`, sempre como **hipóteses não validadas**. Nenhuma tabela ou perfil é alterado.
- O modelo Qwen 2.5 3B configurado hoje **não faz visão**. Mesmo que o scanner já compare os pixels RGB, Ollama recebe só a lista dos sinais; não pode detectar sozinho artes redesenhadas.

## Limitações honestas

- Mudança de arte e de nome **simultaneamente** sem outra evidência pode deixar a carta sem correspondência. Não usar ID numericamente igual como fallback.
- A métrica visual inicial é SHA-256 de pixels RGB idênticos. Artes recoloridas, redesenhadas, com zoom ou paleta diferente exigem algoritmo visual tolerante numa etapa posterior; hash diferente não prova que sejam cartas distintas.
- Os perfis precisam estar importados e com o catálogo reconhecido pelo parser. ISO desconhecida/incompatível não pode ser anunciada como identificada.
- Sem o Ollama instalado, o comparador determinístico continua funcionando e a revisão opcional mostra indisponibilidade.
- O navegador normal não consegue chamar o backend; a tela funciona no aplicativo Windows local autenticado.
- Correspondências por nome ou arte NÃO autorizam reutilizar efeitos, drops e fusões de um mod em outro.

## Testes de regressão

`tests/test_dueltrace_card_matcher.py`: match de Flower Wolf em IDs diferentes, arte única idêntica com nome alterado, nomes repetidos, alterações de ATK/DEF, placeholders, hashes de arte repetidos, ausência de fallback por ID, token da API, cache, paginação e falta de ISO.

`tests/test_dueltrace_card_match_ai.py`: respostas falsificadas do Ollama com IDs inventados são descartadas, pares fora da lista são ignorados, o modelo não roda sem candidatos ambíguos, falha JSON não altera nada e modelo com caracteres inválidos é bloqueado.

## Próximos objetivos

1. Validar na máquina Windows com dois mods reais (p.ex. Original e Remaster X15). Conferir comparações de cartas reais antes de aceitar resultados como equivalência.
2. Adicionar similaridade visual tolerante a alterações de cor/paleta e arte parcial, com detecção de colisões e confirmação do usuário; manter os dados originais intactos.
3. Implementar fluxo explícito de aprovação de **correspondências específicas**, vinculadas aos dois SHA-256, e permitir consulta contextual em Biblioteca, Mão e Fusões. Não migrar drops ou receitas por padrão.
4. Preservar o motor de Spoils/RANK ao vivo validado em duelos: dez ranks originais para Original/FM13/outros, apenas três no Remaster X15 exato.

## Prompt para continuidade

> CONTINUAR DUELTRACE v0.9.2. Repo: https://github.com/guibatoni/appassist, branch `feature/dueltrace-v092-cross-mod-card-matcher`. A Biblioteca de Mods ganhou o **Identificador Universal de Cartas** para comparar duas ISOs com catálogos SLUS e artes WA já extraídos. O comparador utiliza nomes únicos normalizados, pixels RGB únicos e atributos para sugerir equivalências entre IDs diferentes. Nunca usa igualdade numérica de IDs como prova, não transfere fusões/drops/efeitos nem modifica perfis. Há filtro de confiança e paginação. Ollama `qwen2.5:3b` é opcional, recebe apenas 12 pares ambíguos em metadados, e devolve hipóteses whitelisted sem validação automática. Confirmar PR/HEAD/CI/testes e build Windows antes de anunciar release; validar com Original/X15 reais, melhorar comparação visual de artes alteradas e só depois introduzir aprovação individual de equivalências. Preservar o RANK ao vivo (10 classes originais fora do SHA exato X15), mãos, fusões, scanner, atualizador e privacidade local.
