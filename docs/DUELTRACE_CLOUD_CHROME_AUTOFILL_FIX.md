# DUELTRACE Cloud Alpha v0.2.1 — Chrome/Autofill Connector Pairing Fix

## Problema reproduzido a partir da captura do usuário

A senha temporária aparecia como bolinhas dentro do campo, mas o contador `Chave recebida: 0 caracteres` não mudava. Isso acontece quando o gerenciador de senhas/preenchimento automático do navegador altera o valor visível do input sem disparar os eventos que atualizam o estado React. A versão v0.2.0 tentava conectar usando exclusivamente o valor antigo em estado (`pairKey`), que estava vazio, retornando antes de consultar a API.

## Correção v0.2.1

- Ao clicar em **Conectar ao computador**, a chave é lida diretamente do `HTMLInputElement` via `useRef`, mesmo que o Chrome a preencha sem `onChange`.
- O campo deixou de ser controlado pelo estado React; o contador agora é apenas visual e atualizado em input, foco, blur ou clique.
- O botão mostra claramente o estado de inicialização da interface e não depende do contador para permitir o clique.
- A chave temporária permanece apenas na memória volátil do navegador durante a sessão. Após conectar, o input é apagado.
- Autocomplete configurado como nova senha para reduzir preenchimento automático indevido.
- Testes regressivos adicionados, preservando a estrutura visual v0.2.0.

## Teste Windows

Inicie o Connector e o Next.js a partir desta branch, mantendo o Connector em `127.0.0.1:8765` e o site em `127.0.0.1:3000/cloud/`.

Se a chave for preenchida automaticamente, clique **Conectar ao computador**: a implementação lê o valor real do input e não apenas o contador. Em caso de falha, será mostrado o erro, como conexão ausente, chave incorreta ou origem não permitida.

O Chrome pode manter uma senha antiga de sessão anterior; sempre use a chave exibida pelo Connector atualmente executando. Não compartilhe a chave nem a salve em navegadores públicos.

Não houve deploy público, alteração na versão Windows, implementação de assinatura ou upload de arquivos de jogos.
