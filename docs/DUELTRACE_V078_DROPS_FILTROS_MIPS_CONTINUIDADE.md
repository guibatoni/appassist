# DUELTRACE v0.7.8 — Drops por RANK, filtros das bibliotecas e execução MIPS

Data de desenvolvimento: 03/11/2026.

Repositório: https://github.com/guibatoni/appassist

Branch: `feature/dueltrace-v078-rank-drops-filters-evidence`

Base preservada: `feature/dueltrace-v077-mips-rank-safe-updates` (PR #27, commit `15b3ba4a6779ac03d40a3c6ff862ac3f267ca57c`).

## 1. Drops corretos por oponente e RANK

O programa já extrai os 39 oponentes e 117 tabelas com peso total
2048 de cada mod compatível. **Não há equivalência universal entre
os três bancos brutos e os rótulos Z-POW/S-POW/S-TEC.**

Nesta etapa:
- `scanner/dueltrace_drop_rank_evidence.py` compara drops observados após
  um duelo ao conjunto de cartas com peso positivo nas tabelas extraídas
  para o **mesmo oponente e o mesmo SHA**.
- Cartas que aparecem em mais de um banco não são usadas para concluir
  equivocadamente a correspondência do RANK.
- Duas ou mais observações distintas, com pelo menos dois oponentes e
  cartas exclusivas do mesmo banco, criam uma **sugestão** de associação,
  rotulada explicitamente como corroborada manualmente, não como
  mapeamento executável definitivamente confirmado.
- O modelo do X15 mantém seus rótulos apenas quando a identidade da ISO
  é a conhecida; se uma recompensa anotada divergir do banco esperado,
  a aba Drops exibe o alerta.
- Em `get_duel_evidence` e `record_duel_result`, observações ficam
  exclusivamente no diretório local `rank_observations/<SHA>.json`;
  não se enviam ROMs, dados de RAM nem nomes locais para a internet.
- A seção "Conferir drops obtidos em duelo" oferece campos:
  oponente, RANK apresentado, tipo de vitória, ID da carta recebida
  e pontuação mostrada (opcional).

## 2. Filtros de todas as bibliotecas

Biblioteca de Cartas:
- Ordenar por ID, ATK decrescente, DEF decrescente, tipo ou alfabética.
- Filtrar por tipo da carta.
- Reordenar todas as cartas antes da paginação e limpar seleção fora
  dos filtros ao trocar de mod.

Biblioteca de Fusões:
- Ordenar e filtrar pela **carta resultante**, por ID, ATK, DEF, tipo e
  nome alfabético, em todas as receitas antes da paginação.
- API Python validada e protegida por token de sessão do pywebview.

Biblioteca de Drops:
- Ordenar por ID, ATK, DEF, tipo e nome alfabético antes da paginação.
- Filtrar pelo tipo da carta, oponente, tabela bruta, nome/ID.
- Preservar peso, probabilidade, offset do WA e dados da ISO ativa.
- Nenhum atributo ausente é substituído por números fabricados.

Arquivos principais: `scanner/dueltrace_library_sort.py`,
`scanner/dueltrace_drops.py`,
`scanner/dueltrace_web_bridge.py`,
`scanner/dueltrace_web_security.py`,
`web/components/desktop/desktop-page.tsx`,
`web/components/desktop/drops-page.tsx`,
`web/lib/desktop.ts`.

## 3. Validação de RANK durante duelos

- O motor existente lê contadores de RAM e projeta pontos de RANK
  somente nos modelos compatíveis e calibrados (ou identificados
  por hashes, após confirmação de LP).
- Em `get_rank`, uma amostra recente de projeção de pontos e
  contadores pode ser preservada para comparação posterior com a nota
  efetivamente observada pelo jogador após uma vitória por LP.
- O módulo `scanner/dueltrace_drop_rank_evidence.py` mostra quantos
  duelos apresentam projeções de pontos e RANK coerentes com valores
  relatados manualmente, e quantos divergem.
- `scanner/dueltrace_mips_duel_trace.py` lê logs de instruções MIPS
  realmente executadas exportados do depurador do emulador.
  Exige linhas com `PC=0xXXXXXXXX`, qualidade mínima (múltiplos
  endereços, ao menos 30 amostras), e compara os PCs com candidatos
  extraídos do SLUS do mesmo mod.
- Nova ação "Importar log MIPS de duelo" na aba Drops. Permite
  vincular o trace ao último resultado registrado explicitamente
  pelo usuário; os traces brutos não são salvos no catálogo.
- Mesmo com PC observado e pontos iguais, **não declarar automaticamente
  a rotina MIPS de RANK como confirmada**. É necessário provar o
  fluxo de dados que liga aquele PC à leitura da tabela de pontos,
  à soma final, aos rótulos e ao resultado exibido no jogo.
- Nenhum teste sintético prova que a lógica de qualquer mod foi validada
  em uma partida real do ePSXe; essa medição deve ser executada no
  computador do jogador, com a ISO específica.

## Segurança e limites

- Exige sempre SHA da ISO ativa; não mescla bancos de mods.
- API da UI é autenticada por token aleatório, sem execução remota
  nem rota HTTP de mutação.
- Logs externos limitados a 8 MiB e extensão .log/.txt, somente leitura.
- Não incluir ROMs, SLUS ou WA de terceiros no GitHub.
- O Windows Preview continua não assinado; a política de não
  ignorar alertas de Chrome/Defender permanece.
- Atualizações online de produção ainda exigem instalador oficial
  Authenticode que corresponda ao certificado instalado.
- É necessário testar com X15, FM13 e FM Original reais.
- CI deve aprovar todos os testes Python, Next.js, ZIP, dependências
  e Microsoft Defender na branch antes de merge/publicação.

## Próximos passos

1. Abrir cada ISO real no DUELTRACE Windows; extrair os 117 bancos e
   comparar drops de dois ou mais duelos de oponentes diferentes.
2. Exportar trace do emulador ao finalizar duelos com pontuações
   conhecidas; confirmar PCs realmente executados e correlacionar
   os acessos de memória à tabela do WA, com análise de fluxo MIPS.
3. Construir regras e mapas de contadores individualmente verificados
   para cada mod distinto do X15, nunca assumir fórmulas pelo nome.
4. Testar filtros com 722 cartas e centenas de receitas/drops no Windows,
   incluindo paginação e cards sem atributos numéricos.
5. Assinar a primeira versão comercial, lançar instalador confiável e
   testar atualização de ponta a ponta sem contornar proteções.
6. Criar próximo prompt de continuidade e linkar commit+PR+CI final.

## PROMPT DE RETOMADA

> Continue DUELTRACE Windows v0.7.8 no GitHub
> https://github.com/guibatoni/appassist, branch
> `feature/dueltrace-v078-rank-drops-filters-evidence`, baseada
> em `feature/dueltrace-v077-mips-rank-safe-updates` PR #27.
> Preserve WebUI, leitura ePSXe, biblioteca de cartas, fusões 2–5,
> drops, molduras WA por ID, perfis SHA e atualizador seguro.
> A v0.7.8 acrescentou ordenação por ATK, DEF, tipo e alfabética
> e filtro exato por tipo nas três bibliotecas, aplicados
> corretamente antes da paginação. A aba Drops agora permite
> registrar os resultados dos duelos (oponente, RANK, recompensa,
> pontuação, tipo de vitória) e comparar contra as tabelas de peso
> extraídas da ISO, sem atribuir nomes Z/S a grupos desconhecidos.
> Um banco de evidências local por SHA registra discrepâncias,
> observações ambíguas e sugestões corroboradas manualmente,
> além de comparação dos pontos previstos pelo leitor de RAM
> com a pontuação mostrada após o duelo. Agora é possível
> importar um log de execução MIPS do depurador, identificar PCs
> candidatos que realmente aparecem no trace e correlacioná-los
> ao último duelo registrado. **Isso ainda não comprova
> causalidade MIPS nem suporte universal aos RANKs**; é
> necessário validar o fluxo de dados da tabela ao cálculo da
> classificação e executar X15, FM13 e Original no Windows.
> Consultar CI do HEAD antes de declarar aprovação, corrigir
> eventuais regressões, preservar segurança, não subir ROMs
> ao GitHub, não distribuir executável não assinado ao público.
> Finalizar com novo prompt contendo branch, PR, commit, testes,
> entrega e pendências.
