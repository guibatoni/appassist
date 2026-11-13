# DUELTRACE v0.19.5 — Preview

## Novidades
- Nova aba **Decks Salvos** com loadouts nomeados da ISO ativa, incluindo quantidade e lista das 40 cartas.
- Ao salvar um deck no Memory Card, o DUELTRACE abre automaticamente o loadout recém-salvo.
- Busca por nome ou ID da carta no deck atual e nos loadouts salvos.
- Fusões do deck com miniaturas dos dois materiais e do resultado, com visualização de informações por clique.
- Filtro por nomes/IDs das cartas envolvidas nas fusões e seleção de 1, 5, 10, 20, 50, 100, 200 ou todas.

## Melhorias
- Aba Decks fica focada no deck do Memory Card; Decks Salvos organiza os loadouts de montagem.
- O filtro de fusões cobre toda a lista de pares possíveis do deck, sem o limite antigo de 80 resultados.
- Pesquisa nos loadouts encontra tanto o nome do deck quanto as cartas que ele contém.
- Loadouts são cópias locais vinculadas à ISO e permanecem disponíveis sem alterar saves do ePSXe.
- Mantidos a leitura em segundo plano, biblioteca, fusões ao vivo, RANK e emulador ePSXe.

## Correções
- Elimina o corte silencioso dos resultados de fusão na página Decks.
- Salvamento abre diretamente o deck identificado, sem depender da seleção manual de uma lista.
- Navegação independente entre Decks e Decks Salvos, sem duas abas destacadas ao mesmo tempo.
- Nenhum Memory Card é modificado durante a consulta dos loadouts; não há escrita na RAM.

## Limitações
- Os loadouts são modelos de referência: não alteram automaticamente o deck do ePSXe.
- Salvamento atual usa somente as 40 cartas de um save válido selecionado no Memory Card.
- Receitas de fusão não confirmadas para um mod continuam sinalizadas como provisórias.
- Sem API remota, transmissão de RAM ou recursos PCSX-Redux nesta versão.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição somente com autorização expressa do desenvolvedor.
