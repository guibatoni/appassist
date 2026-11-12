# DUELTRACE Cloud Connector v0.5.1 — correção de seleção ISO/BIN no Chrome

## Defeito observado pelo usuário

Ao selecionar uma ISO no painel local do Chrome, o navegador abriu `http://127.0.0.1:8765/local/action` e recebeu `{"error":"Ação de origem não autorizada"}`.

Este erro era produzido antes da execução do seletor nativo de arquivo em `_browser_action`, não indicava falha da ISO nem do ePSXe. A validação exigia `Origin: http://127.0.0.1:8765` até mesmo quando um navegador compatível enviava um POST sem cabeçalho `Origin`.

## Correção

- Mantida a exigência do Host exato `127.0.0.1:8765` e cliente local.
- Quando o navegador informa `Origin`, ele **deve** corresponder exatamente à própria origem. `Origin: null` ou diferente não são aceitos.
- Se `Origin` estiver ausente, aceitamos apenas `Sec-Fetch-Site: same-origin` ou `Referer` no próprio `/local/`, sempre com **token CSRF temporário e válido**.
- `Sec-Fetch-Site: cross-site` continua sempre negado; origem conflitante, Host falso, token errado, requisição sem comprovação local e origem remota continuam negados.
- O cabeçalho `Referrer-Policy` da **página local** passa de `no-referrer` para `same-origin`. Isso permite comprovação no próprio localhost, sem compartilhar referências com outros sites. API `/v1/*` mantém suas regras originais.
- Testes integrados reproduzem a tentativa de importar ISO via POST sem Origin, o caso de Memory Card sem Origin, e os ataques negativos acima.
- O motor Python, o `UiFilePicker`, as regras de leitura da ISO e os dados existentes não são alterados.

## Como usar o novo build

1. **Feche a janela do Connector antigo** para liberar a porta 8765 e feche a guia de erro.
2. Extraia **todo** o ZIP v0.5.1 numa pasta nova. Não misture a pasta `_internal` antiga com o novo EXE.
3. Execute `DUELTRACE-Connector.exe`.
4. No Chrome, confirme o texto `v0.5.1` em `http://127.0.0.1:8765/local/`.
5. Entre em **Biblioteca de Mods → Selecionar ISO/BIN**, escolha o arquivo pelo seletor Windows e então ative o mod importado.
6. Se ocorrer nova falha, envie a tela do navegador e a mensagem exibida no Connector. Não envie uma chave nem arquivos pessoais.

## Limites da validação

Os testes automatizados reproduzem as formas do pedido HTTP, mas não capturam os cabeçalhos específicos do Chrome do usuário. A correção só pode ser considerada validada em campo após funcionar na máquina Windows real.

Nenhum arquivo ISO, BIN, RAM, Memory Card ou diretório de usuário é transferido para a nuvem por esse fluxo.
