# DUELTRACE v0.19.3 — Preview

## Novidades
- **Leitura contínua em segundo plano:** mão, fusões ao vivo, RANK e candidato de adversário continuam sendo acompanhados ao navegar por qualquer aba.
- O monitor inicia junto com o DUELTRACE Windows, antes da abertura da Central de Duelo.
- Deck ativo validado no ePSXe também é atualizado em segundo plano quando o jogo foi iniciado pelo DUELTRACE.
- A tela principal e os visores pop-up compartilham os mesmos resultados recentes; abrir outra aba não reinicia o acompanhamento.
- Um indicador em cada tela mostra que a leitura ao vivo permanece em segundo plano.

## Melhorias
- Motor Python em duas rotinas de leitura: mão/RANK e adversário, independentes do estado das páginas React.
- Cache de curto prazo por ISO, evitando múltiplas leituras de RAM quando duas janelas estão abertas.
- Invalidação automática da mão ao trocar de ISO, perder conexão com ePSXe ou encerrar o aplicativo.
- Mantidos Memory Card, biblioteca de mods, fusões, drops e configurações da versão ePSXe 0.19.2.

## Correções
- Ao retornar de Fusões, Biblioteca, Drops, Oponentes ou Decks, mão e RANK não precisam reiniciar sua calibração por causa da troca de aba.
- Visores flutuantes deixam de disparar leituras duplicadas; consultam o mesmo estado compartilhado.
- Resultados antigos não permanecem exibidos indefinidamente quando a leitura para.
- Nenhum recurso PCSX-Redux foi reintroduzido; o emulador continua sendo exclusivamente ePSXe.

## Limitações e privacidade
- O motor funciona enquanto o DUELTRACE Windows estiver aberto e houver perfil de ISO ativo; leituras exigem ePSXe em execução.
- Oponente e RANK permanecem provisórios quando o mod não tiver mapeamento validado.
- Ferramentas de diagnóstico forense e qualquer envio remoto continuam dependendo de consentimento separado.
- Nenhuma porta, API HTTP, WebSocket, integração com nuvem ou gravação de RAM é ativada nesta versão.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição do aplicativo somente com autorização expressa do desenvolvedor.
