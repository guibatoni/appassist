# DUELTRACE — Etapa 28: triagem forense de consistência (somente observacional)

Data da análise: 06/11/2026. Base: branch `feature/dueltrace-v097-private-evidence-sync-v27`, PR #75. Etapa 28 é isolada e **não autoriza merge na main**.

## Evidência do repositório remoto privado (não copiar JSON integral ao repositório de código)

Repositório privado do usuário `guibatoni/dueltrace-evidencias`, caminho `reports/61d58d835246/79dd2bf007694191.json`.

- Uma sessão remota estava **em execução** ao ser verificada; o arquivo era atualizado a cada novo upload.
- Na consulta das 22:37:35 UTC, o arquivo registrava **127 amostras, 39 mudanças**, 39 leituras de mão e 39 leituras de adversário por âncora. 
- `candidateIdsObserved=[5]` mesmo com **4 pares distintos de campos interpretados como LP**, e diversas mãos alteradas.
- O relatório permanecia com `verifiedOpponentMapping=false`, `verifiedRankGroups=false`, `mayActivateDrops=false` e `mayActivateRank=false`. Nenhum evento gravado de RANK pronto no momento dessa consulta.
- Esses valores representam **campos candidatos**. Os offsets de LP e ID vêm do mapa do jogo original; o sucesso do `known_hand_anchor` demonstra que a base da mão coincide, mas **não** valida a semântica dos outros endereços no GOG.
- O `romFingerprint` é uma identificação da ISO selecionada no aplicativo, não autenticação independente da ISO executada no emulador.

A persistência do valor `5` é uma evidência útil de constância, não uma prova de qual oponente está em jogo. Não usar o índice da tabela de 39 nomes nem escolher um dos 40 blocos físicos como se estivessem mapeados. Os 160 bancos candidatos não viram drops reais sem demonstração de endereçamento e RANK.

## Alteração de código (não modifica o algoritmo de jogo)

- `scanner/dueltrace_live_forensics.py`: gera agregados de eventos sanitizados (quantidade de mãos distintas, pares de campos legados que parecem LP, IDs candidatos observados, capturas de RANK). Não exporta cartas da mão, bytes, endereços, caminhos, PCs ou segredos.
- A flag `candidateStableDespiteHandAndLpFieldChanges` só indica constância de um candidato apesar de mudanças em **pelo menos 2** mãos e **2** pares de campos com **ao menos 3** eventos de candidato; não valida ID ou LP. Os indicadores de oponente/drop/fusão verificados permanecem `false`.
- `dueltrace_web_bridge.get_live_diagnostics_status()` retorna `forensicReview` calculado na memória, sem alterar o JSON enviado ao GitHub nem o contrato `LiveDiagnosticsRecorder.export_json()`.
- A interface da Biblioteca de Mods mostra, quando aplicável, aviso explicando a constância e a necessidade de evidência independente.
- Regressões em `tests/test_dueltrace_live_forensics.py` usam dados **sintéticos**; testes devem passar no CI da branch antes da Preview Windows.
- Biblioteca 722/722, artes, leitura RAM, status de RANK e ativações de drops continuam sem alterações.

## Gargalos reais que a análise evidenciou

1. **ID de adversário:** é necessário rastrear a instrução MIPS que define/lê o ID no executável GOG, ou outra fonte independente verificável que o vincule ao nome do adversário mostrado no duelo. A âncora da mão é insuficiente.
2. **Limite do duelo:** variações da mão e dos campos legados de LP não distinguem infalivelmente um novo duelo de cartas jogadas/compradas ou de estados antigos na RAM. É preciso prova de início/fim por evento do motor do jogo ou trace executado, sem inferir a partir de heurística isolada.
3. **Drops e RANK:** o fluxo atual não registra autonomamente a carta recompensada, o RANK efetivo nem o endereço da tabela de recompensas lida no momento da vitória. Antes de associar as 160 matrizes, precisamos de evidência de execução do caminho MIPS e de recompensa.
4. **Fusões:** alterações da mão sozinhas não distinguem fusão de cartas jogadas, substituição ou compra. É necessário observar inputs e output em evento de fusão, ou extrair e validar a estrutura de fusões na ISO, sem extrapolar receitas do jogo original.
5. **Privacidade:** a telemetria atual deve continuar sanitizada e autorizada, num repositório privado; nenhum dump de RAM/ISO/executável/arte/tokens é enviado.

## Ordem de trabalho sugerida sem repetir duelos manuais

1. Executar a triagem automática das sessões já existentes, comparando alterações observadas, e sinalizar possível baixa discriminação do byte candidato sem declará-lo errado.
2. Implementar no scanner **local** uma investigação de proveniência do campo do adversário na ISO GOG, associando referências MIPS e estruturas físicas; manter todas as respostas em quarentena enquanto não houver prova dinâmica.
3. Só depois capturar contadores/IDs de recompensa e contexto de fusão quando houver offsets/routines validados, sem mexer nas funcionalidades já confirmadas.
4. Manter PRs em draft, validar CI, atualizar backups em `docs/` e Biblioteca do ChatGPT ao fim de cada etapa.

## Monitoramento externo configurado

Há uma automação do ChatGPT que verifica novas evidências no repositório privado **a cada hora**, quando disponível, e notifica somente descobertas relevantes. Não é uma conexão MIPS ao vivo nem uma execução contínua desta conversa. O DUELTRACE continua o envio próprio (aproximadamente a cada minuto enquanto o diagnóstico está ativo).
