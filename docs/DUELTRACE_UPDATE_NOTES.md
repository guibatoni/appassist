# DUELTRACE v0.19.2 — Preview

## Novidades
- DUELTRACE Windows voltou a ser **exclusivamente ePSXe**, abandonando os experimentos com PCSX-Redux das previews v0.19.0 e v0.19.1.
- Base recuperada integralmente da versão Windows estável de trabalho v0.18.0: sem menus, servidores, processo, PIN/PID nem dependências para PCSX-Redux.
- Preparação documental da futura API de snapshots ePSXe para o DUELTRACE Cloud, sem abrir portas, enviar RAM ou ativar conexões não autorizadas.

## Melhorias
- Mantidos ePSXe, leitura de mão, fusões, RANK, biblioteca, Memory Card, imagens, decks e janelas.
- Atualização direta de v0.19.0/v0.19.1, com configurações e dados preservados; primeiro extraia em pasta separada.
- A integração futura com a versão web será baseada em dados derivados e validados, e não em acesso livre à RAM, ISO/BIN ou ao disco.

## Correções
- **Retirados** a seleção PCSX-Redux.exe, o formulário da porta 8080 e a descoberta de processos PCSX-Redux.
- **Retirados** todos os adaptadores REST e de RAM do PCSX-Redux, bem como as rotinas de inicialização do emulador que não funciona com os mods testados.
- Configurações, leitura de RAM e inicialização ePSXe restauradas sem a opção alternativa.
- As previews antigas de PCSX-Redux foram descontinuadas; nenhuma atualização nova deve recuperá-las.

## Compatibilidade e privacidade
- ePSXe Windows e mods com perfis RAM/ISO validados; não é possível prometer leitura automática de todos os mods sem validação.
- O ePSXe não oferece uma API remota de RAM documentada que tenha sido confirmada nesta investigação.
- Um site comum não pode ler a RAM de um processo Windows externo sem uma integração nativa autorizada.
- O DUELTRACE Windows desta versão não oferece API HTTP pública, não abre portas para o navegador e não modifica a RAM.
- Os dados do jogo continuam locais, salvo ações explícitas do usuário em funcionalidades previamente existentes.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição do aplicativo somente com autorização expressa do desenvolvedor.
