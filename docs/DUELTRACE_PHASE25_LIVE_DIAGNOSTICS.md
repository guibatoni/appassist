# DUELTRACE — Etapa 25: Live Diagnostics (primeira integração)

## Escopo entregue

O DUELTRACE agora tem um painel **Live Diagnostics** na Central de Duelo. A coleta é **opt-in**: o jogador clica em **Iniciar diagnóstico**, o motor monitora a sessão local com amostras aproximadamente a cada 3 segundos e o botão **Parar diagnóstico** interrompe a coleta. O painel exibe quantidade de amostras e mudanças relevantes e permite **Copiar relatório para o ChatGPT**.

O gravador monitora o leitor de mão já funcional, os estados da sonda de ID de adversário e o resultado de RANK que a interface principal já observou. Não cria calibrações de RANK novas, não força win/deck-out, não define IDs de adversários e não habilita drops/fusões.

## Privacidade, limites e acesso remoto

- O log é salvo exclusivamente no diretório local de dados do aplicativo em `live_diagnostics/<SHA da ISO>.json`. A exportação contém somente uma impressão digital curta da ISO e os campos permitidos.
- Campos permitidos: cinco IDs numéricos de cartas, status e ID candidato de adversário, LP e contagens dos motivos de rejeição da RAM, pontuação e rótulo de RANK provisórios já observados. Nenhuma imagem/arte, ISO, binário, dump, ponteiro, caminho do PC, token, PID ou campo de texto arbitrário é exportado.
- Até 360 eventos de mudança e um relatório limitado a 140 KB, com compactação de amostras idênticas. Sem atualização externa, sem requisições HTTP e sem conexão automática com o ChatGPT.
- **O ChatGPT não pode abrir conexões diretas com a memória do Windows pela conversa.** Para receber a evidência aqui, a pessoa copia o relatório pelo botão e o cola na conversa. Uma eventual integração contínua exige serviço remoto autenticado e aprovação explícita, com controle de acesso, limite de retenção, revogação e consentimento separado.
- A coleta é encerrada se a ISO ativa mudar. A sessão não é reativada automaticamente após reiniciar o aplicativo.

## Teste prático

1. Iniciar GOG MOD 2.2 com ePSXe e manter DUELTRACE aberto.
2. Abrir **Início → DUELTRACE Live Diagnostics** e clicar em **Iniciar diagnóstico**.
3. Jogar normalmente. Não precisa informar cartas, RANK nem recompensa.
4. Conferir que os contadores **Amostras / Mudanças relevantes** crescem. Em seguida, clicar em **Parar diagnóstico**.
5. Clicar em **Copiar relatório para o ChatGPT** e colar o JSON nesta conversa para interpretar os estados de RAM e as mudanças.

## Pendências ainda abertas

- Ainda não se provou que `0x8009B361` representa o mesmo adversário no GOG ou que os 40 blocos são indexados pelo byte do emulador.
- O monitor não realiza streaming para esta conversa nem modifica os dados de drops. A associação de IDs e RANK exige evidência executável ou rastreamento MIPS verificado.
- A coleta não contém a RAM completa por razões de privacidade e segurança; ela registra os resultados das sondas específicas já implementadas.

**Nota:** CI Python/Windows é necessária antes da Preview; teste end-to-end com ePSXe real ainda é independente.
