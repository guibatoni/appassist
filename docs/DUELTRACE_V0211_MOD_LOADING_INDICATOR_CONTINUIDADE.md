# DUELTRACE v0.21.1 — indicador de carregamento

Data: 15/11/2026  
Repositório: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v0.21.1-mod-loading-indicator`  
Base: `feature/dueltrace-v0.21.0-remaster121-rank-labels` (PR #125)  
Plataforma: Windows.

## Pedido

Durante o reconhecimento de mods ou o carregamento de recursos, mostrar um indicador discreto em um canto da interface, informando a operação em andamento.

## Implementação

- `web/components/desktop/desktop-page.tsx`: cria um indicador fixo no canto inferior direito, com animação acessível via `role=status` e `aria-live`.
- O componente de Mods comunica a atividade à página principal, mantendo o indicador visível durante navegação entre abas.
- Os rótulos incluem reconhecimento/importação de ISO, atualização de dados, ativação de mod, carregamento do Memory Card, configuração do ePSXe, inicialização do jogo e atualização da lista.
- A inicialização dos dados locais também apresenta indicador.
- `docs/DUELTRACE_UPDATE_NOTES.md`: Patch Notes sincronizadas com a versão v0.21.1.
- `tests/test_dueltrace_preview_version_policy.py`: a checagem da branch válida continua alinhada à versão corrente, sem fixar um número antigo.

## Verificação pendente

Aguardar CI Windows, build e Preview Vercel. Validar visualmente no app Windows que o indicador surge durante importação/reanálise, permanece visível se a pessoa trocar de aba e desaparece ao terminar.
