# DUELTRACE — Biblioteca de drops por carta e atualizador de um clique

**Branch:** `feature/dueltrace-v097-opponent-validation`.

## Biblioteca de cartas
A biblioteca do desktop agora consulta `get_card_drop_sources(card_id)` pela API local protegida. O motor verifica o ID numérico e o SHA da ISO ativa, recupera todas as páginas (até 117 possíveis entradas por carta), ordena pela chance de drop e exibe oponente, RANK, grupo, peso e porcentagem.

Os bloqueios de integridade de `get_drop_catalog` permanecem: são exigidas 722 cartas, 39 oponentes e 117 matrizes válidas. Dados provisórios de mods sem mapeamento confirmado permanecem indisponíveis. RANKs clássicos não comprovados em mods desconhecidos são identificados como sujeitos a validação em duelo.

## Atualizador
O botão **Atualizar agora** autoriza a atualização diretamente, sem confirmação adicional do aplicativo. Continuam obrigatórias a origem autorizada, validação de versão, SHA-256 e identidade do pacote. Alertas de segurança do próprio Windows não são suprimidos.

O helper Windows espera o fechamento do processo, valida o pacote, faz backup dos itens gerenciados (`DUELTRACE-WebUI.exe`, `_internal`, `LEIA-ME-SEGURANCA.txt`), substitui esses itens **na mesma pasta do executável** e reinicia o programa. Arquivos e pastas não gerenciados, inclusive dados pessoais, são preservados. Em falha, tenta restaurar os itens originais.

## Validação e limites
Foram adicionados testes de regressão para filtro exato, paginação interna, isolamento por ISO, autorização da API e preservação de arquivos locais. Ainda precisam ser executados no ambiente de desenvolvimento original, além de integração real Windows e rollback.

O workspace Codex Cloud original não foi acessado, nem seus arquivos não commitados foram inspecionados. O commit foi preparado com `[skip ci]` para evitar o workflow de publicação automática de Preview nessa branch. Nenhuma release foi solicitada.
