# DUELTRACE — janela Windows integrada ao aplicativo

## Implementação

- O ponto de entrada `scanner/dueltrace_web_desktop.py` usa pywebview
  `frameless=True`, `easy_drag=False`, `resizable=True`.
- A área de logo do cabeçalho é `.pywebview-drag-region`: arrastar
  o logo/cabeçalho move a janela, sem arrastar indevidamente os botões.
- Os controles visuais ficam em `web/components/shell/window-controls.tsx`,
  dentro da própria `TopBar`, que permanece visível ao rolar a página.
- A API `ProtectedDesktopApi.window_control(token, action)` aceita somente
  `state`, `minimize`, `toggle_maximize`, `close`; o token é o mesmo já
  protegido para as demais operações. Nenhuma rota HTTP de escrita é criada.
- `close` devolve o resultado da ação antes de destruir a janela; a rotina
  de fechamento para atualizações permanece independente e compatível.
- O estado de maximização é sincronizado por eventos nativos e por consulta
  do controle ao recuperar foco, para exibir o ícone correto ao restaurar.
- `web/components/shell/app-shell.tsx` aplica rolagem na área interna do
  aplicativo, e `web/app/globals.css` define a barra estreita em azul,
  transparência no trilho e destaque ciano ao passar o mouse.

## Validação

Os testes não usam ROMs nem modificam configurações e dados do usuário.
`tests/test_dueltrace_native_window_chrome.py` verifica a lista permitida
de ações, token de sessão, maximizar/restaurar, agendamento do fechamento,
região de arraste, cabeçalho e rolagem. O workflow Windows gera e audita
o ZIP com o pywebview fixado.

Testar manualmente no Windows: mover a janela pela região do logo,
minimizar e restaurar pela barra de tarefas, maximizar/restaurar, fechar,
acessar todas as abas com rolagem, usar controles com teclado, atualizar
o aplicativo na mesma pasta e reabri-lo. O aspecto de redimensionamento e
os comandos de janela do Windows devem ser conferidos no WebView2 real.
