# DUELTRACE v0.9.6 — Investigação de terminadores de nomes do GOG MOD

## Estado de partida

Base: PR #45, branch `feature/dueltrace-v095-partial-iso-evidence`, commit `18542ecc68d89c900e9b8df434d1a17f5ae84f72`. O Remaster X15, FM13 e o Original mantêm seus próprios SHA-256, tabelas e regras de RANK.

A captura real do usuário para **GOG MOD 2.2 – Drop 15 (NDC)** indica:

- Executável `GOG_VNT.223` encontrado como PS-X EXE pelo cabeçalho e pelo `SYSTEM.CNF`.
- Contêiner `GOSD/GOG_SD1.23` selecionado como candidato de WA pelo tamanho (38.148.608 bytes), com 3 matrizes iniciais de pesos compatíveis. O decoder encontrou 117/117 matrizes com soma 2048 e 4.543 entradas estruturais de drops. São candidatas por SHA, **não mapeadas a cartas/nomes confirmados**.
- As amostras de cartas em offsets conhecidos exibem nomes reconhecíveis: `Blue-eys White Dragon`, `Curse of Dragon`, `Dragon Queen of Tragic`, `Buster Dragon`, `Meteor Dragon`, `Light and Darkness Dragon`, `Dark Cavalry`, `C-Crush Wyvern`, `Hyper Psychic Blaster`, `Horakhty`. O relatório mostra 722/722 registros superficialmente plausíveis; não valida atributos nem identidade de todos.
- A tabela de oponentes no índice tradicional (0x328+1..39) **não parece estar ausente**, porque os ponteiros decodificam nomes legíveis. Amostras exibidas: ID 1 `SIMON MURANv`, ID 2 `TEANAv`, ID 3 `JONOv`, ID 10 `PANIKv`, ID 20 `TEANA 2NDv`, ID 30 `ODINv`, ID 39 `PHARAOH ATEMv`; status `invalido_ou_vazio` e 0/39 nomes aceitos.

**Hipótese principal:** problema com o byte de término/código de controle dos textos de oponentes (ou com a extensão de leitura do decoder); o sufixo `v` NÃO deve ser removido sem provas. Priorizar essa hipótese antes de deslocar tabelas.

## Implementado na v0.9.6

- `scanner/dueltrace_name_boundaries.py`: inspeção de até 39 registros consecutivos. Calcula distância até o próximo ponteiro, verifica se `0xFF` aparece antes do próximo registro, registra o primeiro byte ilegível, um trecho de até 8 bytes finais, prefixo legível e contadores de ocorrência dos possíveis bytes delimitadores. Limites de leitura fixos e apenas diagnóstico.
- `scanner/scanner_multiiso.py`: executa o diagnóstico quando o decoder não reconhece cartas e oponentes; preserva estado original de classificação, sem limpar sufixos ou associar registros não verificados.
- `scanner/dueltrace_mod_diagnostic.py`: divulga só 7 amostras (IDs 1,2,3,10,20,30,39), com bytes limitados, contagens agregadas e aviso `validated: false`.
- Next.js: seção **Análise dos terminadores dos nomes** dentro de **Evidências e próximas investigações**, sem carregar o conteúdo da ROM nem arquivos pessoais.
- `scanner/ia_local.py`: Ollama recebe apenas contagens e o byte ilegível mais frequente, nunca os binários. Regras instruem a IA a não eliminar sufixos ou validar nomes por hipótese. Cache de análise é invalidado (schema 7).
- Testes sintéticos: registros com `0xFF` e `0xFE`, prefixo `F8 0A`, arquivos truncados, preservação de `validated: false`; nenhuma ISO comercial é distribuída.

## Interpretação e limitações

Se 38 registros consecutivos não contêm `0xFF` antes do próximo ponteiro e o mesmo primeiro byte ilegível aparece reiteradamente, isso sugere um terminador alternativo. **Não confirma por si só o significado desse byte**. Algumas ISOs podem incluir bytes de controle, cabeçalhos ou versões de nomes. O resultado precisa ser confrontado com nomes mostrados no jogo e com a decodificação de todos os 39 registros.

Mesmo que o decoder de oponentes seja corrigido, o scanner deve validar atributos e identidade das 722 cartas antes de disponibilizar os 4.543 drops candidatos. A classificação de RANK clássico continua preservada para outros mods; as três classificações do Remaster X15 só são aplicadas ao SHA exato do X15. Nenhuma leitura de MIPS ou RAM é habilitada automaticamente.

## Teste seguinte no Windows

1. Instalar a Preview v0.9.6 apenas após CI aprovada.
2. Na Biblioteca de Mods, localizar **GOG MOD 2.2**, clicar **Ler WA_MRG + SLUS novamente** e abrir **Diagnosticar estrutura → Evidências e próximas investigações**.
3. Enviar captura da seção **Análise dos terminadores dos nomes** com `hasFFBeforeNext`, `noFFBeforeNext`, `commonFirstInvalidByte` e amostras.
4. Comparar os dados ao jogo. Só então propor uma rotina de decodificação específica, validada e isolada por SHA/assinatura de layout.

## Prompt de continuidade

> CONTINUAR DUELTRACE v0.9.6, branch `feature/dueltrace-v096-opponent-string-boundaries`. No GOG MOD 2.2, a v0.9.5 extraiu 117 matrizes e 4.543 entradas provisórias do `GOSD/GOG_SD1.23` e revelou nomes legíveis nos ponteiros de cartas e oponentes do `GOG_VNT.223`. Os 39 nomes dos oponentes foram rejeitados pelo decoder tradicional mesmo com amostras como `SIMON MURANv`, `TEANAv`, `JONOv`, `PHARAOH ATEMv`. A v0.9.6 adiciona exame limitado de limites de nomes, terminador FF, primeiro byte ilegível e trechos de bytes finais. A próxima missão é usar evidências reais para investigar a terminação/codificação do GOG e recuperar um decoder verificado; NÃO limpar sufixos ou ativar os 4.543 drops sem comprovar os 39 nomes e o catálogo de 722 cartas. Preservar RANK, Spoils, outras ISOs, Biblioteca, atualizador e segurança. Documentar branch, commit, PR, testes e pendências.
