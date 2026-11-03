# DUELTRACE v0.7.6 — Descoberta automática das tabelas RANK

## Objetivo
Localizar automaticamente, ao importar/reanalisar uma ISO de Forbidden Memories,
as tabelas de pontos de RANK no `DATA/WA_MRG.MRG`, sem aplicar cegamente
a fórmula de um mod a outro.

Repositório: https://github.com/guibatoni/appassist

Branch: `feature/dueltrace-v076-rank-autodiscovery`

Base: `feature/dueltrace-v075-rank-forensics-safe-updater` (PR #25).

## O que foi implementado

1. **Correção de truncamento:** o scanner anterior, quando `with_art=False`,
   limitava o WA a um prefixo cujo final ficava 216 bytes antes da última tabela
   de RANK conhecida. Agora lê integralmente o WA em toda importação, mantendo
   o teto de 96 MiB e não enviando arquivos a nenhum servidor.
2. **Busca por assinatura estrutural:** procura padrões de 10 critérios ×
   5 faixas, cada uma como `<u16 limiar_exclusivo, i16 pontos>`, com a última
   faixa terminando em 32767.
3. **Localização independente do X15:** infere o primeiro offset e o
   espaçamento entre as 40 cópias repetidas; aceita novos offsets e strides,
   não apenas setor 7475 + `0x16D0` e stride 6144.
4. **Verificação de integridade:** recusa estruturas ambíguas, faixas inválidas,
   múltiplas sequências válidas conflitantes, excesso de candidatos e layouts
   incompatíveis. O teto de bytes e limites de candidatos controlam custo.
5. **Verificação por identidade:** só aplica nomes de critérios e bônus
   de RANK do X15 se SHA da ISO, SHA do SLUS, SHA da tabela, offset e stride
   coincidirem com o X15 forense verificado.
6. **Três graus de evidência:** tabela extraída, identidade binária confirmada,
   execução real do duelo. O código agora distingue essas condições:
   a verificação estática NÃO confirma os contadores RAM nem o RANK final.
7. **Interface:** a Biblioteca de Mods indica se encontrou o RANK e o offset;
   a aba Drops mostra os pontos, o hash e o espaçamento da tabela, com aviso
   sobre a validação pendente do executável ePSXe.
8. **Cache:** `ART_PARSER_REVISION=6`, forçando nova análise das fontes ao
   reconstruir perfis gerados pela revisão anterior.
9. **Testes:** amostras sintéticas de tabelas originais, tabela realocada,
   stride de 8192 bytes, alinhamento de dois bytes, tabelas divergentes,
   binários não correspondentes e múltiplos candidatos.

## Evidência e limitações

- Os endereços e hashes do X15 são fundamentados em investigação forense
  anterior de uma ISO real: tabela SHA-256
  `dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0`;
  SLUS SHA-256
  `67ef6a3f7999bc4b0e09f773b07ee1c5da829a4d4686f1f2f6c8d4e2d6425bec`.
- Os novos testes são sintéticos. O ambiente de processamento binário local
  não disponibilizou uma execução direta dos três arquivos reais da Biblioteca
  (X15, FM13, Original Drop x15). Não declarar validação em todos os mods.
- Ler pontos no WA **não prova** que o MIPS do SLUS usa essas tabelas nem
  revela os rótulos Z/S POW/TEC de um mod desconhecido.
- A leitura RAM, a classificação dos resultados e os bônus de vitória por mod
  ainda requerem investigação separada (comparação com instruções do SLUS
  e duelos observados no ePSXe).
- A aplicação Windows Preview continua **não assinada**; não instruir usuários
  a ignorar bloqueios do Chrome/Defender nem redistribuir ISOs.

## Próximas etapas

1. Executar o scanner sobre cada ISO real no Windows, conferir offset, stride,
   hash e as 50 faixas com a pontuação final observada em duelos.
2. Criar um reconhecedor das rotinas MIPS de RANK com assinaturas verificadas
   por mod (sem adivinhar rótulos e resultados).
3. Registrar mapeamento de memória por mod, validar LP + transição de ações
   antes de habilitar projeção de RANK ao vivo.
4. Estudar mods com variações de tabela por oponente: guardar candidatas
   separadas sem produzir uma única fórmula geral.
5. Seguir com assinatura Authenticode e distribuição comercial segura.

## PROMPT DE CONTINUIDADE

> Continue DUELTRACE Windows v0.7.6 no GitHub
> https://github.com/guibatoni/appassist. Branch
> `feature/dueltrace-v076-rank-autodiscovery`, baseada em
> `feature/dueltrace-v075-rank-forensics-safe-updater` (PR #25).
> Foram preservadas as bibliotecas, Drops, fusões 2–5, molduras WA por ID,
> scanner SLUS, atualização segura e perfis SHA. Corrigimos leitura parcial
> do WA (faltavam 216 bytes das tabelas RANK na análise sem arte), agora
> lemos o arquivo inteiro até 96 MiB, detectamos automaticamente 40 cópias
> de uma tabela com 10 critérios e 5 faixas, inferimos offset e stride
> mesmo que um mod os altere e recusamos dados ambíguos ou inválidos.
> A pontuação candidata aparece na aba Drops; nomes e bônus só são
> confirmados quando os hashes ISO+SLUS+WA correspondem ao X15 conhecido.
> Não confundir extração de estrutura com prova de execução MIPS ou RANK
> final no ePSXe. Checar o HEAD e o CI da branch e corrigir falhas antes
> de publicar. Ainda é necessário testar X15, FM13 e Original Drop x15 em
> Windows com seus arquivos reais, analisar as rotinas MIPS de cada mod
> e calibrar leitura RAM e RANK ao vivo. Não redistribuir ROMs e não
> orientar bypass de Chrome/Defender; Preview não assinada não deve ser
> distribuída comercialmente. Ao concluir cada etapa, registrar commit,
> PR, CI, resultados e novo prompt de continuidade.
