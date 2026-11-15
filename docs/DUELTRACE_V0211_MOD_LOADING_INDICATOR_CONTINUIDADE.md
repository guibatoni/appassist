# DUELTRACE v0.21.1 — indicador de carregamento

Data: 15/11/2026  
Repositório: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v0.21.1-mod-loading-indicator`  
Base: `feature/dueltrace-v0.21.0-remaster121-rank-labels` (PR #125)  
Plataforma: Windows.

## Pedido

Durante o reconhecimento de mods ou o carregamento de recursos, mostrar um indicador discreto ao lado da barra de rolagem, sempre na área visível, informando a operação em andamento.

## Implementação

- `web/components/shell/app-shell.tsx`: renderiza o indicador ao lado da barra de rolagem, fixo à janela e fora do contêiner rolável, com `role=status` e `aria-live`.
- `web/components/desktop/desktop-page.tsx` publica a atividade no store compartilhado, mantendo o indicador visível durante rolagem e troca de abas.
- Os rótulos incluem reconhecimento/importação de ISO, atualização de dados, ativação de mod, carregamento do Memory Card, configuração do ePSXe, inicialização do jogo e atualização da lista.
- A inicialização dos dados locais também apresenta indicador.
- `docs/DUELTRACE_UPDATE_NOTES.md`: Patch Notes sincronizadas com a versão v0.21.1.
- `tests/test_dueltrace_preview_version_policy.py`: a checagem da branch válida continua alinhada à versão corrente, sem fixar um número antigo.

## Verificação pendente

Aguardar CI Windows, build e Preview Vercel. Validar visualmente no app Windows que o indicador surge durante importação/reanálise, permanece visível se a pessoa trocar de aba e desaparece ao terminar.
