# DUELTRACE v0.20.0 — Preview

## Novidades
- Novo **overlay nativo de RANK** sobre o ePSXe Windows, transparente, compacto e sem bordas.
- O overlay acompanha a janela de jogo e não intercepta mouse, teclado nem cliques.
- Mostra **RANK previsto** e classificação (ex.: S-POW) quando há leitura coerente em duelo.
- Em fase de calibração, indica **ANALISANDO**, sem inventar pontos de RANK.
- Em Configurações, é possível ativar/desativar o overlay, alterar posição, tamanho e opacidade.

## Melhorias
- Usa o monitor de RAM compartilhado iniciado pelo DUELTRACE; não cria um segundo scanner.
- Segue a área útil (client area) do ePSXe ao mover/redimensionar a janela.
- Oculta automaticamente quando o emulador é minimizado, perde o foco ou a leitura de duelo termina.
- Preferências persistentes no próprio DUELTRACE, com validação estrita e sem exigir plugin no ePSXe.
- Preservadas as abas Decks, Meus Decks, Fusões, Drops, Biblioteca, a leitura em segundo plano e os arquivos de Memory Card.

## Correções
- Sem sobreposição permanente em outros programas; somente ePSXe ativo e em primeiro plano.
- Valores provisórios não são apresentados como resultado oficial do jogo.
- Janelas e processos auxiliares são encerrados junto com o DUELTRACE Windows.
- Nenhum processo ePSXe recebe escrita de RAM, injeção ou interceptação de controles.

## Limitações
- A sobreposição é opt-in: ative-a uma vez em Configurações > Overlay de RANK no ePSXe.
- RANK só é exibido quando o motor já reconheceu um duelo e conseguiu uma leitura plausível.
- O RANK é uma previsão e continua sujeito à validação por ISO; não substitui a pontuação final do jogo.
- Recomendado **ePSXe em modo janela ou janela maximizada**. Fullscreen exclusivo pode ocultar a sobreposição.
- A posição e transparência dependem das janelas nativas do Windows; validar no ePSXe real.
- Emuladores múltiplos simultâneos não são suportados pelo overlay inicial.
- Não existe API pública, transmissão de vídeo, HTTP/WebSocket externo ou compartilhamento remoto.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição somente com autorização expressa do desenvolvedor.
