# DUELTRACE — plano de desenvolvimento e critérios de conclusão

## Base e alcance

Plano iniciado sobre a **Preview v0.9.6**, commit de referência
`aef5a34a595d63d36d89f947ee8c0ec132ca69be`, branch de origem
`feature/dueltrace-v096-opponent-string-boundaries`. O objetivo é evoluir o
produto existente, preservando perfis antigos e recursos já operacionais.
Este documento não anuncia uma release nem comprova compatibilidade de uma ISO.

O README da raiz foi atualizado para apresentar o fluxo WebUI e preservar a
Alpha Tkinter histórica. Para detalhes do desktop, consultar
[web/README.md](../web/README.md), o código e
`.github/workflows/validar-webui-desktop.yml`. A presença de uma implementação
ou de um workflow não estabelece que um teste passou nesta execução.

As informações sobre GOG MOD 2.2 são evidências históricas documentadas nas
versões [0.9.5](DUELTRACE_V095_GOG_PROVISIONAL_DROPS.md) e
[0.9.6](DUELTRACE_V096_GOG_NAME_TERMINATORS.md). Sem o executável, contêiner e
observações reais do jogo, os nomes, IDs, atributos e probabilidades desse mod
continuam pendentes de validação. Não distribuir seus arquivos neste repositório.

## Arquitetura existente

| Área | Componentes principais | Responsabilidade |
| --- | --- | --- |
| Importação e persistência | `scanner/auto_mods.py`, `scanner/importador_perfis.py` | Registro local, perfis por SHA-256, cache e ativação |
| ISO e extração | `scanner/scanner_multiiso.py`, `scanner/fm_deep_assets.py`, `scanner/fm_card_text.py`, `scanner/extrator_fusoes.py` | ISO9660, nomes e atributos, recursos WA, textos e bancos de fusões em layouts reconhecidos |
| Descoberta | `scanner/dueltrace_layout_discovery.py`, `scanner/dueltrace_name_layout_probe.py`, `scanner/dueltrace_name_boundaries.py` | Candidatos e sondagens limitadas; não aprovam identidades por hipótese |
| Catálogo e comparação | `scanner/card_catalog.py`, `scanner/dueltrace_card_matcher.py`, `scanner/dueltrace_drops.py` | Cartas por perfil, correspondências entre duas ISOs e consulta de drops |
| Duelo | `scanner/dueltrace_live_hand.py`, `scanner/dueltrace_fusion_planner.py`, `scanner/dueltrace_rank_*.py` | Mão, receitas, pontuação e auditorias específicas da ISO |
| Interface atual | `web/app`, `web/components/desktop`, `web/lib/desktop.ts` | Início, Mods, Biblioteca, Fusões e Drops, integrados ao motor local |
| Janela e API local | `scanner/dueltrace_web_desktop.py`, `scanner/dueltrace_web_bridge.py`, `scanner/dueltrace_web_security.py` | pywebview, arquivos estáticos e comandos protegidos por capacidade de sessão |
| Interface legada | `scanner/abrir_biblioteca.py`, `scanner/dueltrace_desktop.py` | Alpha Tkinter preservada; não substituir o fluxo WebUI por ela |
| IA opcional | `scanner/ia_local.py`, `scanner/dueltrace_card_match_ai.py` | Hipóteses sobre metadados limitados, sem aprovação de catálogo ou execução de scripts |
| Atualização | `scanner/dueltrace_update_checker.py`, `scanner/dueltrace_preview_updates.py`, `scanner/dueltrace_preview_installer.py`, `scanner/dueltrace_signed_install.py` | Canais, origem, hashes e instalação Windows conforme a modalidade |
| Distribuição | `.github/workflows/validar-webui-desktop.yml`, `tools/security` | Build estático, auditorias, empacotamento, verificação de arquivo e Defender Windows |

`web/lib/data.ts` contém dados fictícios de prévia visual. As telas públicas
devem continuar usando o bridge em `web/lib/desktop.ts` para os dados de jogo.
O navegador de desenvolvimento comum não obtém as permissões do pywebview.

## Estado observado no código de referência

**Implementado** significa que há código e testes de regressão correspondentes;
**experimental** exige evidência adicional; **pendente** não possui aceitação
comprovada. Nenhuma dessas categorias substitui testes reais com cada ISO.

| Recurso | Estado | Limite de confiança |
| --- | --- | --- |
| Importação, cache e perfis isolados por SHA | Implementado | Conferir invalidação do cache quando parser, manifesto ou arquivo mudar; não misturar dados entre perfis |
| Descoberta de executáveis renomeados | Implementado, limitado | Assinatura `PS-X EXE` e `SYSTEM.CNF` são pistas; não validam as tabelas internas |
| Descoberta de contêineres desconhecidos | Experimental | Sondagens WA usam offsets históricos; tamanho e algumas matrizes coerentes não provam identidade |
| Cartas, nomes, artes e textos | Implementado para layouts reconhecidos | Ausência de um decoder não significa ausência de dados na ISO; texto de efeito não prova execução |
| GOG: 39 nomes de oponentes | Experimental, pendente de evidência real | Textos legíveis rejeitados; significado do sufixo `v` e do terminador ainda não comprovado |
| GOG: 722 cartas e 4.543 drops | Provisório | As contagens históricas não demonstram atributos, IDs ou associação corretos; preservar evidências sem ativação |
| Identificador Universal de Cartas | Implementado como candidaturas | Nome, atributos e arte podem sugerir equivalências; igualdade de ID nunca comprova identidade nem autoriza transferência |
| Mão e fusões de 2–5 cartas | Implementado, condicionado ao perfil/leitor | Testes sintéticos não comprovam RAM em qualquer emulador/mod; receitas devem pertencer à ISO ativa |
| RANK/Spoils e dez classes clássicas | Implementado, com graus de confiança | Preservar fórmula e separar score lido, projeção calculada e referência hipotética |
| RANK X15 | Implementado para identidade específica | Z-POW/S-POW/S-TEC exclusivos do SHA-256 X15; não propagar endereços nem regras a outros mods |
| Sondagem RAM legada sem binding | Experimental, requer revisão | A v0.9.0 lê endereço host legado após selecionar um perfil; LP e transições plausíveis não validam o mod |
| Fim de duelo, deck-out e Exodia automáticos | Pendente de comprovação completa | Não inferir vitória/fim a partir de uma estimativa de Spoils |
| Bridge local e interfaces | Implementado | Testar janela, seletor, desconexão e ciclo de processos no Windows; não anunciar funcionamento do pywebview por uma prévia HTTP |
| Ollama desligado | Fluxo determinístico previsto | Testar ausência/timeout/JSON inválido; IA não pode mudar offsets, habilitar recursos nem validar identidade |
| Atualizador Preview/portátil | Implementado, sem assinatura obrigatória | Origem, SHA-256 e identidade do build não equivalem a assinatura de editor; consentimento e aviso devem permanecer |
| Instalador assinado | Fluxo implementado, implantação condicionada | Exige identidade/certificado real e artefato oficial; não inventar editor ou contornar proteções Windows |
| v1.0 e preparação comercial | Pendente | Exige teste Windows real, conteúdo/licenças revisados e ausência de falhas críticas conhecidas |

## Incrementos desta implementação

As mudanças a seguir evoluem a base v0.9.6. Não constituem confirmação real do GOG
nem anúncio de Preview publicada; testes finais e versão devem constar do
relatório da entrega.

- **Limites de nomes:** o trabalho do scanner passa a compartilhar a leitura de
  glifos e a fronteira determinada pelo próximo início físico do texto. O decoder
  conhecido exige `FF` dentro desse limite. O diagnóstico distingue ponteiros
  compartilhados, inválidos ou fora de ordem e preserva o byte/glifo final, sem
  eliminar `v` nem interpretar um terminador novo como fato.
- **Integridade de catálogo:** `scanner/dueltrace_catalog_validation.py` acrescenta
  validação das cardinalidades/IDs, nomes e limites binários de atributos. A
  importação e a API de drops verificam referências únicas, pesos reais das 117
  matrizes e proveniência SHA. Probabilidades derivam dos pesos; dados rejeitados
  conservam evidência provisória. Ver
  [DUELTRACE_CATALOG_INTEGRITY.md](DUELTRACE_CATALOG_INTEGRITY.md). Limites binários
  coerentes não comprovam a semântica das cartas nem a ordem de adversários no
  GOG real.
- **Build independente de Google Fonts:** `web/app/layout.tsx` usa Geist e Exo 2
  locais, mantendo identidade visual, caracteres do português e pesos variáveis.
  Fontes e licenças OFL têm origem fixada por commit no repositório oficial
  `google/fonts` e hashes documentados em
  [web/app/fonts/README.md](../web/app/fonts/README.md). As cópias das licenças em
  `web/public/licenses/fonts/` acompanham o export e o pacote. Essa mudança remove
  o download de fontes durante o build; não contorna verificação TLS nem usa
  fontes simuladas.

## Invariantes para todas as entregas

1. Preservar fórmulas, perfis, compatibilidade e dados locais. Não fazer merge em
   `main` sem autorização.
2. Registrar a origem e o SHA da ISO em toda evidência. Um SHA parcial não é
   identidade suficiente para habilitar um adaptador.
3. Separar candidato estrutural, estrutura validada pelo parser e comportamento
   confirmado no jogo. Um campo de confiança não pode transformar uma hipótese
   em fato por conta própria.
4. Não limpar `v`, pontuação ou outros caracteres para produzir nomes esperados.
   Terminação, glifos, prefixos e limites exigem evidência binária e comparação
   independente.
5. Não habilitar RAM incompatível nem transferir dados entre mods. Auditar o
   leitor legado de forma explícita antes de ampliar suporte.
6. IA nunca executa scripts, aprova tabelas, altera offsets ou preenche dados
   ausentes. Todos os recursos essenciais funcionam sem Ollama e sem Internet.
7. Não publicar ROMs, recursos do jogo, tokens, logs privados ou caminhos pessoais.
   Preservar TLS, assinaturas e checksums das dependências/atualizações.

## Sequência de implementação e aceitação

Os marcos abaixo são lotes de trabalho, não promessa de release. Número de versão,
branch, commit, PR, CI e download só devem ser registrados quando existirem.

| Etapa | Entrega utilizável | Critério de conclusão |
| --- | --- | --- |
| 1 — Nomes GOG | Diagnóstico de limites/terminadores e decoder estritamente comprovado quando possível | 39 registros individualmente delimitados, ponteiros dentro do arquivo, glifos/prefixos explicados, comparação de nomes com o jogo; sem arquivos reais, concluir somente testes sintéticos e coleta de evidências, mantendo validação real pendente |
| 2 — Scanner/layouts | Descoberta extensível e adaptadores isolados | Arquivos renomeados, tabelas deslocadas, truncamento, candidatos múltiplos e falsos positivos testados; orçamento explícito de I/O/memória/tempo; nenhum candidato promovido por tamanho ou IA |
| 3 — Cartas | Catálogo completo com procedência por campo | 722 IDs únicos e válidos no layout, nomes e atributos verificados independentemente; campos ausentes marcados; correspondências entre mods aprovadas por pares de SHA sem migração automática |
| 4 — RANK/Spoils | Leitura e auditoria preservadas por ISO | Regressões 76→B-POW, 29→B-TEC e abertura hipotética 101; fórmula intacta; reset de duelo/PID/ISO, estabilidade e desconexão testados; amostras reais para cada binding e tipo de vitória suportado |
| 5 — Fusões | Sugestões válidas para a mão ativa | Receitas da mesma ISO, slots não reutilizados em cadeias 3–5, equipamentos com regras comprovadas, busca limitada e ranking de resultados; distinguir receita desconhecida e ausência de combinação |
| 6 — Drops/oponentes | Consulta com IDs e pools seguros | Validar cartões e 39 oponentes antes de associar 117 matrizes; preservar 4.543 candidatos históricos; rejeitar IDs/nomes duplicados, SHA divergente e pesos inválidos; confirmar grupos/probabilidades em jogo |
| 7 — Efeitos/rituais/equipamentos | Informação com origem explícita | Texto declarado separado de efeito executado; parser e evidência de jogo para novas rotinas; tradução explicativa sem mudar o nome original |
| 8 — Ollama | Diagnóstico opcional seguro | Respostas malformadas/inventadas/fora da lista rejeitadas; ausência e timeout não bloqueiam scanner; nenhum efeito sobre dados aprovados |
| 9 — Interface | Início focado em mão, fusões e RANK | Estados vazio/carregando/erro/sucesso; diagnóstico em área secundária; navegação, filtros e seletores testados com bridge real Windows |
| 10 — Atualizador | Atualização e recuperação verificáveis | Canais e comparação de versões, origem/tamanho/hash, assinatura quando exigida, ZIP seguro, encerramento, backup, restauração e reinício testados no Windows; aviso de pacote não assinado |
| 11 — Desempenho | Fluxo contínuo estável | Evitar reanálise quando hash/parser/resultados não mudarem; não duplicar polling/tarefas; medir scanner, cache e latência da UI com limites e cenários representativos |
| 12 — Distribuição | Candidato de release Windows revisável | Instalação limpa, desinstalação/atualização, privacidade/termos, logs exportáveis sem dados sensíveis, documentação, assinatura e propriedade intelectual revisadas; licença opcional sem segredos de emissão no cliente |

Licenciamento Patreon, múltiplos emuladores, histórico opcional, coleção por
Memory Card e recomendações estratégicas permanecem posteriores à estabilização.
Não presumir offsets equivalentes em emuladores diferentes.

## Evidências necessárias para fechar o caso GOG

- SHA-256 completo da ISO e dos arquivos utilizados, versão do parser e tamanho
  real do executável. A origem da coleta deve ficar no diagnóstico local.
- Ponteiro/offset inicial e limite de cada um dos 39 registros, distância ao
  próximo registro, prefixo de controle e janela curta de bytes ao redor do fim.
- Mapeamento dos glifos envolvidos, incluindo o byte que hoje aparece como `v`;
  distinguir glifo, controle, sufixo verdadeiro e leitura além do nome.
- Para o último oponente, uma fronteira independente: não usar fim do arquivo ou
  o primeiro terminador encontrado após outro registro como prova automática.
- Nomes exibidos no jogo e amostras de IDs não adjacentes, além de auditoria
  completa dos 722 registros das cartas e seus atributos.
- Relação oponente/pool/carta dos drops e resultados de duelos independentes.
  Soma 2048 comprova somente coerência estrutural do vetor de pesos.

Não é necessário publicar binários. Relatórios compactos e capturas consentidas
podem fornecer evidência inicial; a confirmação do decoder depende da análise
local dos arquivos reais. Enquanto faltar essa evidência, manter os candidatos
íntegros e os recursos não comprovados indisponíveis.

## Validação por entrega

Executar e registrar resultados atuais; não reutilizar contagens da Alpha antiga:

```bash
python -m compileall -q scanner tests
python -m unittest discover -s tests -p 'test_*.py' -v
cd web
npm ci
npm run build
npm audit --omit=dev --audit-level=moderate
npm audit --audit-level=high
cd ..
python tools/security/verify_web_css.py
```

Usar testes focados durante a implementação e a suíte completa antes da entrega.
Na CI Windows, também executar o empacotamento, auditoria do arquivo, verificação
de assinatura quando requerida e Defender descritos no workflow. Testes GUI/RAM
ignorados no Linux devem ser registrados como ignorados, não aprovados.

Cada relatório de entrega deve informar: objetivo e arquivos alterados, versão
implementada (se houver), comandos e resultados com contagens, branch/commit,
PR e CI realmente observados, download somente se publicado/aprovado, limitações
reais e o próximo bloqueio verificável. Falha de acesso à API não comprova estado
de PR, CI ou release.

## Porta de saída para v1.0

A versão estável só deve ser anunciada quando instalação Windows, atualização,
persistência, catálogo dos mods oficialmente suportados, mão, fusões e RANK nos
bindings calibrados passarem pelos testes automatizados e pelos duelos reais.
Nenhuma falha crítica conhecida pode ser omitida. Mods incompatíveis continuam
com diagnóstico claro e dados preservados, sem promessa de compatibilidade
universal.

## Incrementos v0.9.7 desta branch

- Leitura limitada por registro e evidência dos 39 ponteiros/glifos: [nomes GOG](DUELTRACE_V097_GOG_NAME_EVIDENCE.md). Nenhum terminador alternativo ou sufixo foi corrigido por suposição.
- Descoberta com adaptador WA explícito e limites PS-X EXE: [layouts](DUELTRACE_V097_LAYOUT_ADAPTERS.md). Não há adaptador novo GOG comprovado.
- IDs, atributos e matrizes efetivas conferidos antes de associação; API exige catálogo completo: [integridade](DUELTRACE_CATALOG_INTEGRITY.md).
- Leitura de RANK restrita a SHA X15 exato ou binding próprio validado; fórmula preservada: [guardas RAM](DUELTRACE_V097_RANK_RAM_GUARDS.md). A leitura da mão mantém seu mecanismo anterior e precisa de validação por mod.
- Cache geral passa a considerar a revisão do parser mesmo sem extração de artes: [cache](DUELTRACE_V097_SCAN_CACHE.md).
- Atualizador e publicador reconhecem versões explícitas como `v0.10.0`, além de branches compactas históricas, sem ampliar origens autorizadas.
- Fontes Geist/Exo 2 locais, com licenças OFL incluídas na distribuição: [origem e hashes](../web/app/fonts/README.md).
- Auditoria registra um advisory moderado de ferramenta de desenvolvimento sem patch compatível: [dependências](DUELTRACE_V097_DEPENDENCY_AUDIT.md).

Estes incrementos não encerram os critérios reais das etapas 1, 3, 4 e 6.
A próxima validação determinante continua sendo a coleta local do relatório
completo do GOG e a comparação com o jogo no Windows. Build, testes locais,
publicação no GitHub e duelos reais são evidências diferentes.
