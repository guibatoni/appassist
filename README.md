# Forbidden Memories Assistant — MultiMod

Assistente para Yu-Gi-Oh! Forbidden Memories e versões modificadas, com launcher, perfis de jogo, leitura do ePSXe, contadores, cálculo de pontuação e rotas de fusão.

## Estado atual
- **Launcher:** v0.3 (pré-lançamento), com patches incrementais, verificação SHA-256, backup e reinício do Assistente após a atualização.
- **Assistente:** núcleo MultiMod v0.1, em validação.
- **Atualizações pelo GitHub:** ainda dependem de uma Release pública com os anexos `patch.zip` e `update-manifest.json`. Criar o repositório sozinho não ativa atualizações.
- **Código-fonte:** o pacote preparado para publicação será enviado separadamente; este commit apenas inicializa o repositório.

## Segurança e dados
O projeto de código não distribui ISOs, executáveis comerciais, Memory Cards, saves nem artes extraídas do jogo. Patches devem modificar apenas arquivos permitidos dentro de `app/` e respeitar dados locais.

## Publicação do código
Extraia o pacote preparado **Código-Fonte MultiMod v0.3 — appassist** e execute `PUBLICAR_GITHUB.bat` com Git for Windows instalado e autenticado. O script clona este repositório, copia somente o código permitido e cria um commit.

## Configuração do launcher
Repositório GitHub: `guibatoni/appassist`.

> Projeto de fãs, não afiliado ou endossado pelos detentores de Yu-Gi-Oh!.
