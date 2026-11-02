# Scanner MultiISO v0.3.6 — Correção de desempenho e progresso

## Problema observado (Windows)
O usuário informou que a Biblioteca de Mods permanecia mais de cinco minutos na mensagem "Lendo ISO", especialmente com a imagem `Yu-Gi-Oh! FM Original (Drop x15).bin` (~518 MB).

A captura não demonstra um loop infinito. A inspeção do código apontou operações caras e um comportamento inesperado:
- leitura de disco em setores de 2 KiB com seek para cada setor;
- carregamento completo do contêiner `WA_MRG.MRG` mesmo quando as tabelas reconhecidas ficam antes dos ~15,6 MB;
- hash SHA-256 calculado duas vezes para a mesma imagem;
- importação manual que também iniciava a varredura de toda a pasta de ROMs;
- ausência de progresso visual.

## Correções
- O leitor de disco lê setores em blocos de até 2.048 setores físicos por operação.
- `WA_MRG.MRG` agora é lido até o maior offset necessário ao layout X15 conhecido (atualmente 15.554.240 bytes), não na íntegra; o relatório diferencia `hash_wa_prefix` de hash completo.
- O SHA-256 é calculado em streaming uma única vez por imagem, com progresso a cada ~32 MB.
- A importação individual processa **apenas a ISO/BIN selecionada**; `Monitorar` ativa explicitamente a varredura da pasta.
- A Biblioteca mostra etapa de processamento e barra de progresso.
- Monitoramento só reabre automaticamente se o usuário tiver ativado a opção; botão `Parar` desliga.
- Testes com setores sintéticos ISO2048, Mode1/2352 e Mode2/2352, prefixo WA, hash único e testes de perfis. Não distribuímos ISO comercial.

## Instalação
1. Feche o Assistente e a Biblioteca de Mods para interromper a análise anterior; feche o processo caso esteja ocupado. Isso não altera ISO/saves.
2. No launcher, verifique a versão e atualize via `guibatoni/appassist` para **v0.3.6**.
3. Abra o Assistente e a Biblioteca de Mods (Ctrl+Shift+M). **Não precisa reinstalar o hook da Biblioteca**.
4. Para testar uma ROM isolada, clique em **Parar** (se estiver monitorando) e depois **Importar ISO/BIN**. Selecione uma imagem.
5. Observe a mensagem de etapa e a barra de progresso. Quando completar, os dados aparecem no perfil; estruturas desconhecidas são explicitamente parciais ou não reconhecidas.
6. Só depois experimente **Monitorar** para analisar a pasta inteira, uma ISO por vez.

## Limites conhecidos
- Isso reduz leituras desnecessárias, mas NÃO garante tempo máximo de análise; a velocidade depende do disco e do tamanho do arquivo.
- Não classificar ranks e fusões de mods desconhecidos sem validação independente.
- O SHA de um arquivo de 518 MB ainda precisa ler todos os bytes uma vez.
- A Biblioteca não descobre automaticamente qual ISO está ativa no emulador.
- O recurso de Ollama local não acelera o leitor binário.
- Se a análise ainda falhar, trazer a mensagem de erro completa e o arquivo `relatorio.json` gerado.
