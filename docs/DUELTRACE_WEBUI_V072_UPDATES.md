# DUELTRACE WebUI 0.7.2 Preview — botão Verificar atualizações

## Onde fica
Botão `Verificar atualizações` no cabeçalho de todas as telas da WebUI v0.7.2 Preview.
Depois do clique, o painel informa versão atual, canal, última release estável
publicada no repositório oficial e resultado da comparação semver numérica.

## Privacidade e segurança
- A verificação **só é executada por ação explícita do usuário**; não há polling nem agendamento.
- Consulta apenas metadados públicos do endpoint HTTPS fixo da API GitHub:
  `https://api.github.com/repos/guibatoni/appassist/releases/latest`.
- Sem envio de dados de ISO, cartas, RAM, nomes de mods, IDs da máquina ou dados de licença.
- Usa conexão com timeout de 7 segundos, corpo limitado a 256 KB e recusa redirecionamento.
- Exige tag semver simples e URL exata dentro do repositório GitHub oficial.
- Por segurança, o botão **não baixa nem instala executáveis** e não altera arquivos locais.
- `Ver versões oficiais` abre somente `https://github.com/guibatoni/appassist/releases/latest` no navegador padrão.
- As chamadas da WebUI para o motor Python exigem o mesmo token de sessão da aplicação.
- Quando offline, informa falha de consulta em vez de inventar um status atualizado.

## Preview versus estável
- Versão deste build: `0.7.2 Preview`.
- Última versão estável confirmada durante implementação: `v0.6.6`.
- Uma Preview com número superior à estável mostra `preview_ahead`, **não** avisa para atualizar para versão inferior.
- Se uma versão estável futura superar a instalada, mostrará `update_available` com botão para abrir as releases.
- O sistema não monitora automaticamente artefatos de GitHub Actions. Prévias de CI não são releases estáveis.
- Uma versão estável de mesmo número que uma Preview pode conter diferenças; nunca alegar identidade binária.

## Antes da distribuição comercial
Adicionar assinatura Authenticode do executável e instalador e autenticação do
manifesto de atualização antes de permitir downloads/instalações automatizados.
Nenhuma configuração deve pedir que clientes desativem Chrome Safe Browsing ou Windows Defender.
