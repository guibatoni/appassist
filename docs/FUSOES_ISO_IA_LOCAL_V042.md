# MultiMod v0.4.2 — Fusões por ISO e apoio de IA local

## Fonte do formato de dados
Documentação pública do formato de fusões em `WA_MRG.MRG`:
- [fmscrambler — DataScrambler.cs (MIT)](https://github.com/forbidden-memories-coding/fmscrambler/blob/master/FMLib/Randomizer/DataScrambler.cs)
- [Forbidden Memories Toolkit — fm_parse_cards.py](https://github.com/randi-raharja/forbidden-memories-toolkit/blob/main/scripts/fm_parse_cards.py)

São sete bancos documentados, em offsets do WA: 0xB87800, 0xBFD000, 0xC72800, 0xCE8000, 0xD5D800, 0xDD3000, 0xE48800. Cada um pode conter índice de 722 ponteiros e pares compactados de 10 bits.

**Cuidado:** o formato é conhecido para a família FM de 722 cartas. Mods novos podem mudar a organização, deslocar os bancos ou introduzir exceções. O parser sinaliza incompatibilidade; nunca presume que resultados sejam universais.

## Alterações
- `scanner/extrator_fusoes.py`: lê até a última região relevante do WA e procura receitas com validação rigorosa de ponteiros, quantidade e IDs; analisa os sete bancos e compara SHA-256 das listas decodificadas.
- `scanner/investigador_iso.py`: inclui resumo da extração no relatório e salva arquivo local `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\investigacoes\<sha>.fusoes.json`.
- `scanner/ia_local.py`: quando o Ollama estiver instalado, recebe resumo limitado: banco, offsets, hashes, contagem, divergência, exemplos. NÃO recebe ISO nem executável e não pode validar uma fusão por conta própria.
- Biblioteca: botão **Buscar fusões na ISO**, aba **Candidatas (fusões)**, pesquisa por ID/nome, informação de quantas linhas existem e quantos bancos coincidem.
- Candidatas permanecem fora da aba **Fusões** e fora do overlay até uma confirmação **individual**, depois de reproduzir a fusão no jogo e digitar o ID real do resultado.
- O catálogo de receitas aprovadas é restrito ao SHA da ROM. Trocar de mod mantém separação de tabelas.
- Confirmação de uma receita atualiza somente a receita, não o banco inteiro; a aba técnica e o overlay recebem o índice correto.
- Não altera ISOs, saves, Memory Cards ou dados de partidas. Não inclui nenhum arquivo do jogo no GitHub.

## Teste no Windows
1. Feche Assistente/Biblioteca; atualize pelo launcher para **v0.4.2**.
2. Abra a Biblioteca por Ctrl+Shift+M; selecione o **FM Original (Drop x15)**.
3. Clique em **Buscar fusões na ISO**. Aguarde o processamento local; não exige Ollama.
4. Abra **Candidatas (fusões)**. Confira contagem, nomes e quantidade de bancos coincidentes.
5. Repita com **FM 13** e **Remaster X15**, comparando as quantidades e relatórios separados.
6. Para testar a IA, instale o [Ollama](https://ollama.com/) no Windows e obtenha um modelo, por exemplo `ollama pull qwen2.5:3b`. Com o serviço ativo, use **IA local: investigar** ou marque **IA automática (local)** para analisar relatórios de novos mods.
7. **Somente se você reproduzir de fato uma fusão no jogo**, selecione a candidata e clique **Confirmar receita observada no jogo**. Digite o ID real do resultado e confirme. Apenas essa receita poderá ser utilizada no Assistente.
8. Se o banco aparecer incompatível, não substitua arquivos por versões X15 e não force validação; encaminhe o relatório JSON de investigação (contém metadados e receitas extraídas, não a ISO).

## Limitações verificadas
- O parser documentado funciona para o layout histórico, mas **não foi testado com as três ISOs reais no Windows**.
- Os testes de CI usam imagens de memória sintéticas, não ROMs de terceiros.
- Bancos coincidentes são evidência estrutural, não confirmação em gameplay.
- A IA local não faz engenharia reversa autônoma garantida; ela investiga relatórios do parser.
- A fusão pode depender de condições adicionais do jogo; uma fórmula extraída e decodificada não garante sucesso em todos os cenários.
- A confirmação individual por observação vale para a ISO escolhida, não valida o jogo ativo automaticamente.
- Se reimportar uma ISO do zero, confirme se o perfil preservou as receitas revisadas; o sistema ainda não oferece migração/mesclagem de anotações de fusão após uma reextração integral.
