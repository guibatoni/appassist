# DUELTRACE Cloud Alpha 0.2.0 — Interface do Windows reutilizada

**Objetivo:** navegador Chrome com visual coerente com DUELTRACE Windows, sem trocar código ou releases Windows.

## Alterações

- A página `/cloud/` agora utiliza o `AppShell` original: fundo `bg-temple.png`, moldura iluminada, logotipo, TopBar e Sidebar com o mesmo layout responsivo.
- O menu contém as mesmas oito entradas do aplicativo Windows: Início, Biblioteca de Mods, Biblioteca de Cartas, Fusões, Drops, Oponentes, Decks e Configurações.
- Controles nativos de janela, de arrastar o Windows e de atualização de EXE não são exibidos no navegador. O DUELTRACE Windows continua com eles inalterados.
- As páginas Cloud usam classes visuais compartilhadas `panel`, `btn-ghost`, `btn-gold`, `field`, cards com bordas e ícones. Biblioteca mostra imagens locais, paginação e diálogo de detalhes; Fusões mostram material A, material B e resultado lado a lado; deck, mão, oponentes e drops passam a exibir imagens e dados da ISO.
- **Conectar ao computador:** o botão não fica bloqueado silenciosamente enquanto a chave tem poucos caracteres. Um clique mostra erro claro; a interface exibe tamanho da chave, progresso e erros compreensíveis.
- Requisições de leitura usam tempo limite; importações de ISO podem demorar mais e têm limite próprio. Chaves de sessão continuam apenas em estado transitório React, nunca em armazenamento do navegador.
- O Connector e os dados privados permanecem inteiramente no computador do usuário.

## Como atualizar o protótipo

Baixe esta branch atualizada ou use `git pull`, execute `python scanner/dueltrace_cloud_connector.py` no primeiro PowerShell. Em um segundo PowerShell, na pasta `web`, execute:

```powershell
npm.cmd ci
npm.cmd run dev
```

Chrome: `http://127.0.0.1:3000/cloud/`. Cole a **chave inteira** exibida na janela do Connector e clique no botão. Em caso de falha, o formulário detalha o erro. Não compartilhe a chave.

## Escopo e verificação

O visual do **chrome do aplicativo** (topbar, logo, fundo, sidebar e moldura) é compartilhado diretamente, evitando duplicação. Os módulos de operação web ainda adaptam a interação para as rotas JSON locais; nem todos os detalhes específicos da interface desktop (pop-ups nativos, configurações de janela, ações avançadas) estão disponíveis no navegador. Isso deve continuar como uma tarefa explícita, não ser apresentado como 100% de paridade funcional.

Uma compilação aprovada no CI não substitui o teste visual no Chrome e o teste real do ePSXe no Windows.
