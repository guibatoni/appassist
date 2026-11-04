# DUELTRACE v0.8.6 — Spoils, Drops limpos e atualizações sem assinatura obrigatória

Base: v0.8.5, PR #35, commit `3e2dbbc7a695ba964ab6f871494a70418dd70933`.  
Branch: `feature/dueltrace-v086-spoils-drop-cleanup`.

## Solicitações

1. Remover da aba **Drops** a seção de pontuação de RANK e o painel **Conferir drops obtidos em duelo**.
2. Permitir atualizações automáticas sem exigir assinatura digital do instalador.
3. Reutilizar a fórmula anterior de **SPOILS** das conversas e auditorias da calculadora v9/v9.4/v9.5.

## 1. Interface Drops

`web/components/desktop/drops-page.tsx` mantém exclusivamente o **catálogo de drops**, probabilidades por oponente e filtros de RANK, nome/ID, ATK, DEF, tipo e ordem alfabética. Foram removidos o formulário de registro de resultados, as comparações de pontos, snapshots, importação de traces e diagnóstico de execução MIPS **dessa tela**. As APIs de auditoria e dados locais anteriores não foram apagadas; apenas saíram da aba Drops. Não se eliminou o filtro de RANK de recompensa das cartas.

## 2. Calculadora de Spoils recuperada

A nova `scanner/dueltrace_spoils_manual.py` **reutiliza as regras existentes de `dueltrace_rank_live.RULES`**, extraídas da ISO Remaster X15 na investigação de 29/10/2026 e registradas em `RELATORIO_SPOILS_X15.md`. Não foi criada uma tabela alternativa:

- Pontuação inicial: **50**.
- Vitória por LP: **+2**; vitória por deck-out: **−40**; vitória por Exodia: **+40**.
- 10 critérios: turnos, ataques efetivos, vitórias em defesa, cartas viradas, magias, armadilhas, cartas usadas/sacadas, LP restantes, fusões e equipamentos.
- Os pontos são a soma da base, ajuste de vitória e pontuação de cada critério; as faixas de classificação exibidas dependem da ISO selecionada (X15 versus clássica).
- A calculadora manual é apresentada na **Central de Duelo**, independente do leitor RAM e do mapeamento MIPS.
- Não desbloqueia contadores automáticos ou autoriza modelos desconhecidos.
- Ataques efetivos são destruições de monstros inimigos em posição de ataque, não ataques diretos.

**Histórico da conversa e cautela:** foram reportadas comparações numéricas 48/48, 46 previsto contra 45 observado e 42/42 na calculadora anterior, além de duelos relatados como 95 Z-POW, 90 S-POW, **50 S-TEC** e 2 S-TEC. Essas observações foram preservadas como evidências, mas há conflito: as bandas **atualmente aprovadas para X15 na v0.8.1** determinam Z-POW em 95+, S-POW de 50 a 94 e S-TEC abaixo de 50. Portanto, um resultado do jogo relatado como **50 S-TEC** não deve ser reclassificado silenciosamente como correto; exige conferir pontuação e classe diretamente no jogo. Nesta etapa, a fórmula e as bandas existentes **não** são alteradas.

## 3. Atualização sem assinatura obrigatória

As Previews já podem atualizar por meio de pré-releases públicas oficiais com SHA-256 do pacote e identidade do build, após confirmação.

A v0.8.6 amplia o fluxo com suporte opcional a **ZIP portátil de release estável**, chamado `DUELTRACE-WebUI-Windows.zip`, com `digest` SHA-256, URL fixa do repositório, tag versionada, commit SHA e metadados embutidos do build. As assinaturas Authenticode não são obrigatórias para esse pacote (instaladores assinados legados ainda são compatíveis como alternativa).

O atualizador exige confirmação explícita, não desativa Defender/SmartScreen, valida a origem, evita downgrade, impede extração perigosa e prepara substituição com backup/rollback. É esperado que releases antigas, sem ZIP portátil válido, não possam atualizar automaticamente até serem publicados novos pacotes. A reinstalação manual da primeira versão com atualizador continua necessária em PCs com builds anteriores à v0.8.5.

## Pendências reais

- Validar a troca/reinicialização automática em Windows fora da CI.
- Conferir o rank final real em Remaster X15, Original e FM13 no ePSXe. Resolver a discordância histórica de 50 pontos e as diferenças de 1 ponto.
- Confirmar que o sistema original e mods utilizam **exatamente** as regras numéricas encontradas no X15, sem supor identidade por nome da ISO.
- Verificar identidade da ISO executada no emulador e evidências de endereço RAM/MIPS antes de liberar leitura ao vivo para novos mods.
- Preservar dados pessoais locais, Biblioteca, Fusões, Molduras, scanner, drops e segurança de distribuição.

## Prompt para próxima conversa

> CONTINUAR DUELTRACE v0.8.6 no repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v086-spoils-drop-cleanup`. A aba Drops foi simplificada: mantém o catálogo com busca, porcentagens e filtros de RANK/ATK/DEF/tipo/alfabético, mas remove conferência de drops e pontuação de RANK. A Central de Duelo recebeu calculadora manual de SPOILS baseada **nas regras já extraídas da ISO X15** (base 50; LP +2, deck-out −40, Exodia +40; 10 critérios, sem RAM); classificação segundo ISO selecionada. O botão de atualização suporta Previews e ZIPs estáveis públicos com digest SHA-256 e commit verificados, **sem assinatura obrigatória**, após consentimento, sem contornar Defender ou SmartScreen. Confirmar CI, commit, PR e resultados antes de declarar aprovado. Próximas tarefas: testar updater em Windows real e confrontar calculadora com duelos reais (95, 90, 50, 2 e divergência 46/45), em especial contradição de 50 pontos S-TEC versus cutoff v0.8.1; só então ajustar um comportamento comprovadamente divergente. Não inventar endereços MIPS/RAM, não alterar fórmula/bandas sem evidência; concluir com versionamento, PR, testes e pendências.
