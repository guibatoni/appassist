# DUELTRACE — Comparação cruzada de três auditorias forenses (07/11/2026)

## Proveniência

- **Galaxy of Gods NT 2025 — controle positivo**: relatório JSON integral colado pelo usuário nesta conversa em 07/11/2026; fingerprint `8954b9d60327`. Não estava presente em `dueltrace-evidencias/reports/iso-forensics/` na verificação feita nesta data. Usuário confirmou anteriormente compatibilidade funcional com este mod em jogo (cartas, adversários, fusões e drops). Isso é **evidência de teste do usuário**, não `verifiedInGame` gerado pela sonda.
- **Rising of Wicked Gods 1.3.5**: leitura por conexão GitHub do arquivo privado `guibatoni/dueltrace-evidencias/reports/iso-forensics/06b3a87fe7c2.json`, envio `2026-11-07T13:09:12+00:00`.
- **Enhance Edition Final4**: leitura por conexão GitHub do arquivo privado `guibatoni/dueltrace-evidencias/reports/iso-forensics/6a1a897db35c.json`, envio `2026-11-07T12:59:57+00:00`.
- Todos os três relatórios indicaram `exactSha256Matched=true`. Não commitar as ISOs, nomes de cartas, artes, receita de fusões, tokens, RAM bruta nem o JSON completo dos relatórios privados no repo de código.

## Comparação observada

| Métrica | Galaxy | Rising | Enhance |
|---|---:|---:|---:|
| fingerprint | 8954b9d60327 | 06b3a87fe7c2 | 6a1a897db35c |
| tamanho da mídia (bytes) | 160872096 | 115212720 | 115043376 |
| setores PS1 | 2352 | 2352 | 2352 |
| arquivos indexados | 11 | 9 | 9 |
| contêiner WA (bytes) | 38000816 | 38148608 | 38000816 |
| cartas | 722 | 722 | 722 |
| registros de adversários | 39 | 39 | 39 |
| formato da lista de adversários | conventional | FD/u16/FF | FD/u16/FF, 1 exceção +1 |
| matrizes de recompensas | 117 | 117 | 117 |
| famílias 39×4 | 1 única | 1 única | 2 janelas possíveis |
| base do bloco (hex) | 0xE9B000 | 0x2421800 | null (ambígua) |
| stride adversário (bytes) | 6144 | 6144 | null (ambígua) |
| stride de matriz (bytes) | 1460 | 1460 | null (ambígua) |
| fusões decodificadas | 18553 | 5555 | 24953 |
| bancos de fusão equivalentes | 7/7 | 7/7 | 7/7 |
| pares não ordenados contraditórios | 0 | 3 | 0 |
| artes grandes | 722 | 722 | 722 |
| miniaturas | 722 | 722 | 722 |
| duplicadas divergentes | 6 | 56 | 7 |
| hits heurísticos MIPS RANK | 1070 | 998 | 994 |

**Cuidado com o campo tamanho**: verificar o valor exato de Rising antes de usar a tabela como evidência persistente; o relatório remoto é a fonte de verdade. Os três relatórios têm `verifiedInGame=false`, `opponentMappingVerified=false`, `rankGroupLabelsVerified=false`, `executionConfirmed=false`, e `mayActivateDrops=false`. Isso não significa que o jogo não funcione: é deliberada ausência de comprovação automatizada de associações na telemetria.

## Interpretação técnica

1. **Extração e associação são problemas distintos.** O scanner encontra conteúdos em todas as ISOs, mas localizar 117 tabelas não define nome/ID do adversário associado a cada bloco nem os três rótulos de recompensas.
2. **Galaxy controle**: `weightFamily.base=0xE9B000`, `distinct39Windows=1`, nomes convencionais, bancos sem conflitos. Boa referência de estrutura, mas ainda sem observação MIPS independente registrada pelo laboratório.
3. **Rising**: `weightFamily.base=0x2421800`, `distributionEncoding=plain_deck_masked_drops`, 117 grupos e janela única; três pares de fusões com múltiplos outputs permanecem bloqueados. Não publicar os pares em páginas públicas. A diferença do endereço explica falha da busca limitada ao setor legado.
4. **Enhance**: 40 blocos completos e duas possíveis janelas de 39; nenhum dos dois offsets deve ser promovido sem rastrear índice/lookup real no executável ou evento durante o duelo. Nomes 38+1 aceitos estruturalmente.
5. **MIPS**: `staticCandidates` mede padrões encontrados, não funções executadas; o controle positivo tem 1070, o que motivou ampliar o teto da transmissão privada para 65536 sem desabilitar validações.

## Plano de prova incremental (não inferir resultados)

- Primeiro: instrumentar observação/proveniência do ponteiro ou índice do adversário, emulado com referência ao PC MIPS e ao destino de memória quando disponíveis. O ID candidato fixo 5 do GOG não deve ser tomado como adversário real.
- Segundo: detectar por prova independente qual janela de blocos a Enhance efetivamente usa, sem escolher uma só por 117 somas corretas.
- Terceiro: correlacionar rank efetivamente calculado e recompensa observada para decidir associação bloco→adversário e grupo de drops, incluindo o formato do Rising.
- Quarto: resolver os três pares de fusões conflitantes no Rising por rotina MIPS/experimento em jogo, mantendo quaisquer receitas contraditórias em quarentena.
- Quinto: garantir regressão positiva no Galaxy, protegendo 722 cartas e artes e todas as funcionalidades já confirmadas.

## Restrição de segurança

Nenhuma mudança em `main`, nenhuma ativação de drops ou rank por semelhança estrutural, nenhuma divulgação da mídia; os relatórios permanecem no GitHub privado. Esta comparação é documentação de evidências observadas e planejamento, não garantia de conclusão da engenharia reversa.
