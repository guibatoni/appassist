# DUELTRACE Alpha — Etapa 33: drops de recompensa, fusões e pop-ups

Data: 2026-11-07. Branch: `feature/dueltrace-alpha-reward-discovery-and-popouts-v33`.
Base: PR #80 (Etapa 32A), por sua vez baseado no PR #79.
PR desta etapa: #81 (rascunho). **Não fazer merge na main.**

## Objetivo do produto

O usuário quer lançar um Alpha que extraia (i) **nome/ID dos 39 oponentes**, (ii) **cartas que podem cair de cada oponente por RANK**, e (iii) **fusões**. Não quer as cartas do deck do adversário como se fossem seus drops. Também solicitou calculadora de SPOILS em pop-up utilizável com a janela principal minimizada ou em outras abas, e dois botões para dicas de fusões: abrir pop-up, ocultar/mostrar.

## Engenharia reversa em ISOs reais do usuário

Foram inspecionadas diretamente as ISOs/BIN do usuário via contêiner local. Não publicar arquivos binários nem receitas completas.
Todos os três WA contêm **40 blocos consecutivos de 0x1800 bytes** com quatro matrizes por bloco. **O bloco 0 dos três arquivos é idêntico byte por byte (6.144 bytes)**, SHA-256:
`1b3925724cfbf58197fc79a8b1166387d9a438ffdf35162c8e863b852bd8b4f7`.
O layout histórico indica que o bloco 0 é reservado, portanto o extrator Alpha usa somente os **39 blocos seguintes** e os **três grupos de recompensa** (j=1,2,3). j=0 é deck e **nunca aparece como drop**.

| Mod | SHA prefix | Bloco reservado 0 (WA offset) | Bloco candidato 1 (WA offset) | Rows de drops (>0) | Codec nos 39 adversários | Receitas de fusão estruturais |
|---|---|---|---|---:|---|---:|
| Galaxy Of Gods NT 2025 | 8954b9d60327 | 0xE99800 | 0xE9B000 | 8666 | deck plain, drops x15_masked | 18553 |
| Rising Of Wicked Gods 1.3.5 | 06b3a87fe7c2 | 0x2420000 | 0x2421800 | 4901 | deck plain, drops x15_masked | 5555 |
| Enhance Edition Final4 | 6a1a897db35c | 0xE99800 | 0xE9B000 | 4543 | deck e drops plain | 24953 |

- Cada matriz: 722 `uint16` little-endian, stride `0x5B4`, soma dos pesos convertidos = 2048.
- Interpretar peso `w` como porcentagem estrutural `w*100/2048`.
- Três bancos físicos por oponente no formato original: `S/A POW`, `B/C/D POW/TEC`, `S/A TEC`. **Não comprovado que mods alterados usem a mesma rotulação em tempo de execução.**
- Galaxy e Rising armazenam as três matrizes de recompensa mascaradas, mas bloco 0 usa plain. Enhance usa plain em todos os blocos.
- Galaxy/Enhance sem pares de fusão contraditórios; Rising 3 pares unordered conflitantes (não mostrar sugestões com esses pares).
- Nomes/IDs provenientes exclusivamente de `profile.opponents` da ISO ativa; se não houver catálogo completo com 722 cartas e 39 adversários, o preview de drops não é oferecido. Associação nome↔ID é **presumida pela ordem física** até provar execução.
- Nenhuma parte desta etapa monitora o deck do adversário ou atribui grupos por mera presença de cartas no deck.

## Arquivos editados

- `scanner/dueltrace_alpha_reward_pools.py`: reconhece SHA do bloco reservado 0 e lê os 39 registros seguintes; valida 117 matrizes e gera só recompensa, com 722 IDs, pesos, grupo e source_offset. Falha fechada quando sentinel ausente, estrutura ambígua ou matriz corrompida.
- `tests/test_dueltrace_alpha_reward_pools.py`: fixtures sintéticas normal/masked, sentinel e corruptions.
- `scanner/dueltrace_web_bridge.py`: método `_alpha_bundle` seleciona WA da ISO cadastrada, valida SHA completo, limites e 7 bancos; mantém cache por SHA/tamanho/mtime/perfil; `_combined_fusion_recipes` mescla receitas do perfil com candidatas sem sobrescrever contradições e remove os 3 pares conflitantes do Rising. O fallback de drops alimenta a UI **sem alterar o perfil salvo ou flags de ativação**.
- `scanner/dueltrace_drops.py`: catálogo estrutural Alpha marcado `provisional`, mantendo original caminho de dados verificados; `mayActivateDrops=False` e `opponentMappingVerified=False` no Alpha.
- `scanner/dueltrace_web_security.py`, `scanner/dueltrace_web_desktop.py`: comandos de janela e preferências exigem token de sessão; duas janelas pywebview independentes, só com rotas local/allowlist e token injetado em origem local; sempre-no-topo, não dependem de aba principal.
- `web/app/ferramentas/calculadora/page.tsx`, `web/app/ferramentas/fusoes/page.tsx`, `web/components/desktop/floating-tools.tsx`: SPOILS manual + RANK, sugestões duplas/cadeias em janela nativa.
- `web/components/desktop/desktop-page.tsx`: botão de calculadora no cabeçalho e painel RANK, dois botões para fusões (abrir pop-up, ocultar/mostrar), indicação de fusões provisórias.
- `web/components/shell/app-shell.tsx`: shell sem sidebar para as duas rotas.
- `web/lib/desktop.ts`: tipos, métodos protegidos, indicação de provenance.
- `tests/test_dueltrace_web_bridge.py`, `tests/test_dueltrace_drops.py`, `tests/test_dueltrace_native_window_chrome.py`: regressão de cache/associação, fusões conflitantes, persistência opt-out e comandos nativos protegidos.
- `.github/workflows/validar-webui-desktop.yml`: build precisa gerar ambas as rotas dos pop-ups.

## Como testar Windows

1. **NÃO substituir a pasta estável**; usar ZIP Preview privada desta branch após CI/teste do Defender.
2. Importar/ativar Galaxy, Rising ou Enhance (cadastradas com SHA exato, 722 cartas e 39 oponentes extraídos).
3. Abrir aba **Drops** e selecionar adversário e grupo/RANK. A UI deve dizer `ALPHA` e `provisional` em mods ainda não homologados. Mostrar somente 3 bancos de recompensa, NUNCA o deck.
4. Abrir aba **Fusões**, checar quantidade de receitas e pares; Rising deve omitir os 3 pares contraditórios. Não substituir uma receita validada manualmente quando o banco apresentar contradição.
5. Na Central de Duelo usar **Ocultar dicas/Mostrar dicas**; fechar/reabrir app e confirmar que a preferência persiste. Clique **Abrir dicas em pop-up**, minimizar principal, checar atualização de mão/fusão com ePSXe em duelo.
6. Clique **Calculadora em janela** no cabeçalho ou no painel de RANK. Testar os dez campos SPOILS, botão Calcular, live RANK opcional e pop-up independente durante troca de abas/minimização.
7. Reiniciar com outra ISO e confirmar que nenhuma fusão/nome/drop vaza do perfil anterior.

## O que está pendente, sem mascarar

- Identidade adversário↔nome e grupos POW/TEC dos mods ainda **não possuem comprovação de execução do jogo**, embora agora exista assinatura estrutural forte e layout original conhecido. UI rotula como Alpha provisório, sem ativar suporte de RANK ao vivo.
- O sentinel retail exato pode ser alterado por outros mods: nesse caso o extrator não inventa dados; ampliar detecção por signatures/flow de execução em evolução futura.
- A capacidade de pop-up nativo foi compilada em CI Windows; ainda requer teste visual real em WebView2/ePSXe, inclusive minimizar, fechar e reabrir janela. Se a build ainda não concluiu no momento de leitura deste documento, consultar ações do PR #81.
- A fórmula existente de SPOILS foi preservada. Nenhum score foi atribuído por leitura inventada de RAM ou rotina MIPS não confirmada.

## Segurança e backup

- Código em repo **privado**, branch experimental, PR draft. **Sem merge main**.
- Nenhuma ISO, arte, memória bruta, token, receita completa, endereço do host ou outro dado de terceiros enviado ao GitHub automaticamente.
- Os relatórios sanitizados anteriores permanecem separados em `guibatoni/dueltrace-evidencias`.
- O usuário pediu backup em sua Biblioteca: pasta `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/`.
