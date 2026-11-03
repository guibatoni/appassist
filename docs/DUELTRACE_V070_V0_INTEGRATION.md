# DUELTRACE 0.7.0 — Prévia da integração v0 com o aplicativo Windows

## Origem visual
Código importado da branch `v0/web-ui-dueltrace`, criada pelo v0/Vercel. Preserva cores, molduras egípcias, gradientes, identidade, responsividade e ilustração do templo.

## Motor do aplicativo
O projeto continua usando o mesmo Python existente em `scanner/`, os mesmos perfis em `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod`, o mesmo leitor de RAM somente leitura do ePSXe, o mesmo índice de fusões e o mesmo mecanismo de importação de ISOs.

O React/Next.js é compilado em arquivos estáticos no diretório `web/out`. O executável Windows experimental usa pywebview/WebView2 para abrir esses arquivos por um servidor que escuta EXCLUSIVAMENTE em `127.0.0.1`, com porta escolhida pelo sistema operacional. Não depende do site Vercel nem precisa de internet para consultar a mão, os mods ou as fusões.

Os comandos de importação de ISO, ativação de mod, configuração e inicialização do ePSXe utilizam a API nativa de pywebview, não rotas HTTP. O servidor local publica somente HTML/CSS/JS estáticos e imagens PNG extraídas da ISO do **perfil ativo**. Não publica caminhos completos de arquivos, chaves, efeitos não verificados ou conteúdo da ROM.

## Telas
- **Início:** cinco posições da mão, nomes e atributos do perfil, fusões diretas e cadeias de três a cinco cartas, resultados ordenados pelo motor Python. Se a RAM não estiver disponível, a tela não mostra cartas fictícias.
- **Biblioteca de Mods:** lista perfis reais, contagens comprovadas, importa ISO/BIN por diálogo nativo, ativa o perfil após confirmação quando requer revisão, escolhe o ePSXe.exe e inicia o jogo.
- **Biblioteca de Cartas:** pesquisa, ordenação, paginação e detalhes reais; mostra efeito somente com `effect_source` rastreável. Imagem local aparece somente se PNG tiver sido extraído e pertencer ao mod ativo; sem isso mostra indicador de arte indisponível.
- **Fusões:** pesquisa e paginação de receitas reais, com origem `extraida_sete_bancos_consistentes` ou `observada_manualmente_no_jogo` exibidas separadamente. Não existem probabilidades fictícias.

A antiga interface v0 usava cartas "c01", "c02", efeitos imaginários e porcentagens de "chance de sucesso". Esses dados NÃO são usados nas quatro telas integradas. Os componentes originais permanecem apenas como referência de design sem rota pública ativa.

## Desenvolvimento
- `web/`: `npm ci` e `npm run build`; Next.js gera o diretório `web/out` usando `output: export`.
- `scanner/dueltrace_web_bridge.py`: adaptador puro Python, testável sem janela.
- `scanner/dueltrace_web_desktop.py`: lança a janela Windows pywebview com os assets compilados.
- `tests/test_dueltrace_web_bridge.py`: testes de proveniência, ausência de dados fictícios, ligação com a RAM, paginação e acesso a imagens de outro perfil.
- `.github/workflows/validar-webui-desktop.yml`: pipeline de build React, testes Python e criação do ZIP Windows experimental.

## Limites e segurança
- Essa etapa é uma **prévia experimental**. A interface antiga 0.6.6 permanece como alternativa e não será removida automaticamente.
- Uma janela WebView2 real e a conexão RAM/ePSXe no computador do usuário precisam ser verificadas manualmente.
- O ambiente Vercel pode hospedar uma versão pública das telas, mas NÃO acessa a RAM do PC, a pasta de mods ou a lista privada de cartas.
- A prévia web sem o motor Python exibe uma mensagem indicando que está desconectada, sem fabricar estados "Sistema OK".
- Ainda não há licenciamento, assinatura de executável nem instalador certificado. Não distribuir ROMs, BIOS ou assets comerciais de terceiros.

## Próximo marco
Validar a prévia Windows no PC do usuário e, somente após correções, considerar tornar essa UI a interface padrão do DUELTRACE.
