# DUELTRACE v0.8.0 — RANKs corretos no Remaster X15 e no sistema original

Repositório: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v080-classic-ranks-and-drop-pools`  
Base: `feature/dueltrace-v079-rank-proof-pipeline` (PR #29).  
Plataforma: Windows/ePSXe. Idioma: português do Brasil.

## Problema relatado pelo usuário

Na aba Drops apareciam os valores internos
`TABELA_1_RANK_DESCONHECIDO`,
`TABELA_2_RANK_DESCONHECIDO`,
`TABELA_3_RANK_DESCONHECIDO`,
e o seletor de resultados dos duelos sempre oferecia apenas os três
RANKs do Remaster X15, mesmo para mods no formato original.

## Dois sistemas de RANK distintos

### Remaster X15 conhecido por SHA
- Z-POW: 95 pontos ou mais
- S-POW: 50–94 pontos
- S-TEC: abaixo de 50 pontos

Cada um usa um dos três bancos WA da versão X15. Estes critérios
de pontuação não devem ser copiados automaticamente para os outros mods.

### Jogo original e mods com padrão clássico
Ordem de classificação:
1. S-POW
2. A-POW
3. B-POW
4. C-POW
5. D-POW
6. D-TEC
7. C-TEC
8. B-TEC
9. A-TEC
10. S-TEC

São **dez classificações, porém apenas três tabelas de drops**:
- Banco 1, `+0x05B4` no registro de cada duelista: S/A POW
  (S-POW e A-POW).
- Banco 2, `+0x0B68`: B/C/D POW/TEC
  (B-POW, C-POW, D-POW, D-TEC, C-TEC e B-TEC).
- Banco 3, `+0x111C`: S/A TEC
  (A-TEC e S-TEC).

Fontes externas de engenharia reversa pública:
- https://github.com/krystalgamer/memories-decomp/blob/master/notes/research/fusion-and-drop-tables/README.md
- https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/notes/rng.md
- https://github.com/Robertdark/FMHelper/blob/main/MEMORY_MAP.md

A posição dos bancos é verificada no modelo original, mas qualquer
mod desconhecido pode ter alterado a lógica do executável SLUS:
a UI indica **layout original presumido**, não prova de execução
e tampouco RANK ao vivo validado.

## Código alterado

- `scanner/dueltrace_rank_system.py`: fonte compartilhada dos
  RANKs, classes de recompensa, ordem das tabelas e conversão
  opcional de pontuação somente após leitura/observação validada.
- `scanner/scanner_multiiso.py`: novas ISOs que não são o X15
  conhecido são escaneadas com os nomes dos três bancos originais,
  sem alterar pesos, probabilidades, offset ou IDs de cartas.
- `scanner/importador_perfis.py`: registra 10 RANKs nos perfis
  clássicos, mantendo `scoring=false` quando a fórmula executada
  não foi confirmada. X15 mantém três RANKs verificados por SHA.
- `scanner/dueltrace_drops.py`: retorna `rankOptions`,
  `groupOptions`, `rankSystem`, `groupLabel` e
  `eligibleRanks`. Aceita filtro `rank`: mapeia os 10 RANKs
  clássicos às três bolsas WA, antes da paginação. Mantém os
  valores internos de grupo da ISO sem alterar registros existentes.
- `scanner/dueltrace_rank_drop_solver.py` e
  `scanner/dueltrace_drop_rank_evidence.py`: correlacionam
  qualquer um dos dez RANKs clássicos com uma das três classes
  de recompensa; observações idênticas ao X15 continuam separadas.
- `scanner/dueltrace_web_bridge.py` e
  `scanner/dueltrace_web_security.py`: filtro autenticado de
  RANK e validação do RANK informado após um duelo contra a
  lista da ISO ativa.
- `web/components/desktop/drops-page.tsx`: substitui o dropdown
  técnico "Tabela de drop" por "RANK da recompensa"; exibe
  3 ou 10 classificações, nomes humanos das bolsas e formulário
  de registro de duelos por mod.
- `web/lib/desktop.ts`: contrato tipado atualizado.
- `tests/test_dueltrace_rank_system.py` e
  `tests/test_multiiso_drops_source.py`: testes de regressão
  de rank, correspondência física do WA, filtro e manutenção de
  dados dos perfis antigos.

## Compatibilidade e limites

- Perfis de mods anteriores que continham `TABELA_*_RANK_DESCONHECIDO`
  não precisam ser apagados: a ponte local converte as etiquetas
  apresentadas na tela a partir da ordem verificada das três
  tabelas de drops, preservando hashes e IDs.
- Nenhuma ISO é distribuída, copiada para a nuvem ou enviada para
  o repositório. Nem o sistema de drops altera os binários.
- A exatidão da estrutura por mod é diferente da confirmação do
  cálculo MIPS ao vivo; dados desconhecidos continuam sujeitos
  aos testes de duelo.
- O Preview Windows não é assinado; não recomendar contornar
  Defender, Chrome Safe Browsing ou exigir execução de arquivos
  bloqueados.
- Testes automatizados são sintéticos; não constituem validação
  de uma nova ISO real no ePSXe.

## Procedimento de aceitação no Windows

1. Executar uma Preview oriunda do workflow oficial, se
   a plataforma permitir instalá-la de forma segura.
2. Selecionar uma ISO Remaster X15 verificada: a aba Drops
   deve oferecer exatamente Z-POW, S-POW e S-TEC.
3. Selecionar mod com padrão original: a aba Drops deve
   oferecer os 10 RANKs na ordem informada acima.
4. Conferir que S-POW/A-POW retornam a mesma bolsa,
   B/C/D POW/TEC compartilham a bolsa intermediária e
   A-TEC/S-TEC usam a bolsa técnica.
5. Testar em perfil antigo sem reimportar a ISO e verificar
   que `TABELA_*_RANK_DESCONHECIDO` não aparece na tela.
6. Registrar duelos nos dois modos e confirmar que um
   RANK de outra versão é rejeitado.
7. Validar novamente os drops reais e os pontos por duelo
   antes de declarar uma variante modificada como comprovada.

## PROMPT DE CONTINUIDADE

> Continue o DUELTRACE Windows no repositório
> https://github.com/guibatoni/appassist, branch
> `feature/dueltrace-v080-classic-ranks-and-drop-pools`,
> baseada na branch `feature/dueltrace-v079-rank-proof-pipeline`
> (PR #29). A v0.8.0 corrige o sistema de RANKs no Drops:
> Remaster X15 conhecido = Z-POW, S-POW, S-TEC;
> mods clássicos = S-POW, A-POW, B-POW, C-POW, D-POW,
> D-TEC, C-TEC, B-TEC, A-TEC, S-TEC. O original usa 3
> bolsas WA, com a ordem física S/A POW (+0x05B4),
> B/C/D POW/TEC (+0x0B68), S/A TEC (+0x111C).
> O seletor de RANK agora filtra a bolsa correta, sem
> criar 10 tabelas artificiais, e os cards apresentam
> nomes humanos mesmo em perfis antigos que armazenavam
> `TABELA_*_RANK_DESCONHECIDO`. O registro manual de
> duelos aceita somente ranks pertencentes ao mod.
> O mapeamento de mods desconhecidos é o padrão original
> presumido, NÃO validação MIPS ou da fórmula ao vivo.
> Conferir o HEAD/CI Windows e resolver quaisquer falhas.
> Preservar gráficos, fusões, filtros, scans, scores,
> modelos SHA, segurança, updater e dados locais. Nenhuma
> ROM ou binário comercial pode ser enviado ao GitHub.
> Após finalizar, produzir novo prompt contendo branch,
> PR, commit, testes, resultados e pendências.
