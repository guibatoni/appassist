# DUELTRACE v0.20.1 — Preview

## Novidades
- O overlay do ePSXe agora utiliza a **mesma fonte Exo 2** e a identidade visual da calculadora do DUELTRACE.
- Pontuação branca com marcador `pts`, letra do RANK destacada e etiqueta POW/TEC com bordas arredondadas.
- Cores idênticas às da calculadora: S magenta, A vermelho, B amarelo, C verde, D cinza e Z dourado.
- Fundo do overlay permanece transparente e os cliques passam direto para o ePSXe.
- O overlay segue disponível em Configurações com controles de posição, tamanho, opacidade e ativação.

## Melhorias
- POW usa fundo vermelho com texto branco; TEC usa fundo azul com texto branco e contorno suave.
- Letras, números e bordas do overlay são desenhados com suavização para acompanhar a interface Windows.
- A fonte Exo 2 já presente no projeto é incluída no aplicativo Windows, sem exigir instalação de fontes no sistema.
- A imagem nativa do overlay é atualizada quando o RANK muda, sem criar nova leitura de RAM.
- Preservadas as abas Decks, Meus Decks, fusões, biblioteca e o conteúdo do Memory Card.

## Correções
- Substituída a tipografia Segoe UI, que destoava da calculadora principal.
- Removida a exibição do RANK como texto branco uniforme; nota e modo seguem o padrão visual do painel.
- Sem alteração dos cálculos SPOILS, RANK, compatibilidade com mods ou dados do emulador.

## Limitações
- Preview Windows, recomendado ePSXe em modo janela ou maximizado; tela cheia exclusiva pode ocultar o overlay.
- O RANK exibido permanece uma previsão: valores não confirmados não são mostrados como resultado oficial.
- A aparência precisa de validação visual no seu Windows com o ePSXe aberto.
- Sem plugin, DLL injetada, gravação de RAM nem conexão remota.
