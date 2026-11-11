# DUELTRACE v0.9.7 — Etapa 48: interface responsiva Windows

## Objetivo

A UI mantém a identidade azul-marinho, ciano e dourado, e agora se reorganiza
pelo espaço realmente disponível. **Não** usamos zoom automático da página:
cartas e textos continuam legíveis e preservam proporções.

| Formato | Exemplos de resolução | Organização prevista |
|---|---|---|
| 16:9 | 1366×768, 1920×1080, 2560×1440 | Sidebar lateral, cartões múltiplos e painel RANK |
| 16:10 | 1280×800, 1920×1200 | Sidebar, colunas adaptáveis e rolagem vertical |
| 4:3 | 1024×768 | Sidebar lateral quando houver espaço; listas com menos colunas |
| 5:4 | 1280×1024 | Layout horizontal tradicional com colunas elásticas |
| 21:9 | 2560×1080, 3440×1440 | Área principal ampliada, mais cartões por fileira |
| 32:9 | 3840×1080 | Corpo central com largura máxima legível de 2100 px |
| 9:16 | 720×1280, 1080×1920 | Menu em grade acima do conteúdo, filtros empilhados, janela vertical |
| Pequena | 360×640 (Windows, pixels lógicos) | Barra superior em duas linhas; navegação acessível, conteúdo rolável |

**Nota:** são configurações de layout, não mudança da resolução física do
monitor. O DUELTRACE adapta-se a redimensionamento, restauração, maximização
e orientação vertical usando CSS; o Windows escolhe a área útil excluindo
a barra de tarefas para estabelecer o tamanho inicial.

## Elementos alterados

- **Janela principal:** removido o mínimo fixo de 1100×700. Dimensões
  iniciais e limites agora são calculados de acordo com a área útil do Windows.
  O usuário continua podendo arrastar, maximizar, restaurar e redimensionar.
- **Cabeçalho:** logotipo, atualizador e controles minimizar/maximizar/fechar
  permanecem visíveis; o atualizador passa à segunda linha em janelas estreitas.
- **Menu:** horizontal lateral para desktops largos; em telas verticais vira
  grade de 3 ou 5 colunas, com todas as abas visíveis, sem esconder ações.
- **Central de Duelo:** as cinco cartas são distribuídas pelo espaço real,
  mantendo ATK/DEF, nomes, sugestões e painel RANK.
- **Biblioteca de Fusões / Drops:** número de receitas/cartões por linha
  cresce ou diminui de acordo com a largura do painel, sem duas colunas
  apertadas apenas porque a resolução total passou de 1024 px.
- **Biblioteca de Cartas:** os detalhes laterais aparecem apenas quando
  existem ao menos 1050 px de largura real na área principal; caso
  contrário, os detalhes ficam abaixo da grade de cartas.
- **Janelas independentes:** visores RANK e Fusões não excedem a área útil
  do monitor na abertura. O usuário ainda pode redimensioná-los.
- **Pop-ups:** preview de cartas e painel de atualização cabem em 9:16,
  permanecem roláveis, e conservam o atraso de 1 segundo e o fundo escuro.

## Segurança e compatibilidade

A mudança é apenas no layout de React/CSS, cálculo do tamanho da janela
e dimensões dos visores. **Não muda** scanner de RAM, ISO, Rank, fusões,
licenças, downloads, rollback ou regras de autenticação. O aplicativo
continua **somente Windows**, não é uma versão Android/iOS.

## QA

Os testes automatizados verificam:

- geometria inicial válida e limites para dez resoluções/proporções;
- janela nunca maior que a área útil; visores respeitam o monitor;
- CSS e componentes oferecem reflow de menu/cartas/fusões/drops;
- controles nativos, pop-up de atualizações, modal de cartas, leitor de
  memória, gerenciador de mods e o botão de atualização são preservados;
- compilação Next.js/TypeScript e testes completos Python/Windows.

**Validação visual manual pendente:** confirmar em um Windows real as telas
360×640, 720×1280, 1024×768, 1280×800, 1920×1080 e 2560×1080;
navegar por todas as abas, abrir os dois visores e o pop-up de detalhes,
testar atualização, rolagem, maximizar/restaurar e teclado. O CI comprova
a compilação e contratos, não substitui inspeção de cada escala DPI.
