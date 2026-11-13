# DUELTRACE Windows 0.19.3 — motor ao vivo em segundo plano

## Problema corrigido
Anteriormente os componentes React `Home` e os pop-ups iniciavam seus próprios timers para `get_hand`, `get_rank_auto` e `get_live_opponent`, que paravam quando a rota era desmontada. Em Fusões, Drops ou Biblioteca, o usuário ficava sem atualização de mão e RANK e, ao voltar, a calibração precisava recomeçar.

## Nova arquitetura

**Origem única:** `scanner/dueltrace_background_live.py`, iniciado uma vez por `dueltrace_web_desktop.main()` **antes de renderizar a primeira página**.

- Trabalhador principal lê mão/fusões e RANK na RAM do ePSXe; atualizações em intervalos aproximados de 1–2 segundos, respeitando o tempo real da leitura.
- Trabalhador independente consulta o adversário candidato (~4,5 segundos), evitando que a inspeção mais lenta interrompa a mão.
- Leituras são feitas pelo motor **Python** já existente, com regras atuais de reconhecimento e perfil do mod, não por cada aba.
- `DueltraceWebBridge.get_hand()`, `get_rank_auto()` e `get_live_opponent()` respondem do cache compartilhado durante a execução Windows.
- Central de Duelo, Fusões, Biblioteca, Drops, Oponentes, Decks e visores pop-up podem ser abertos/fechados livremente. O módulo continua acompanhando a partida até o fechamento do aplicativo.
- O indicador **Leitura ao vivo em segundo plano** fica visível na faixa superior das telas quando o monitor estiver iniciado.
- Após troca da ISO ativa, as leituras da ISO anterior são rejeitadas imediatamente, e o cache expira automaticamente se a varredura ficar indisponível.
- Quando não há ePSXe, são entregues estados de desconexão **sem varrer RAM** até o emulador voltar.
- Captura de evidências, investigação forense, sincronização e envio remoto permanecem sob permissões separadas.

O monitor não altera RAM, BIOS, ISO/BIN, Memory Card ou arquivos do ePSXe. Não abre portas, servidor HTTP, WebSocket nem transmite dados ao DUELTRACE Cloud.

## Testes

`python -m unittest discover -s tests -p 'test_dueltrace_background_live.py' -v`

Incluem: início antes da UI, leitura independente de rotas, atualização de fusões, RANK e adversário, cache único para vários consumidores, expiração e invalidação de ISO, desconexão do emulador, falhas de leitura, fim da aplicação, preservação de status e isolamento de dados por perfil.

## Limitação honesta

Isso garante que o **monitor continue em funcionamento enquanto o DUELTRACE Windows estiver aberto**, independente da tela. Não valida automaticamente RANK ou oponente para todos os mods e não prova que a ISO executada externamente é idêntica à ativada no aplicativo. A primeira leitura de RAM ainda depende de uma mão reconhecível no ePSXe.
