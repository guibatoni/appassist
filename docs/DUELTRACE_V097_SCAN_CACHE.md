# Cache por revisão do scanner

`SCAN_PARSER_REVISION = 7` identifica as regras gerais de descoberta, nomes,
catálogos e drops. A revisão é registrada em todo `relatorio.json`, mesmo
quando a extração de artes está desligada ou o layout não é reconhecido, e
em cada entrada nova do registro de mods.

Uma entrada antiga sem revisão, ou com revisão diferente, é reanalisada na
próxima importação ou descoberta pelo monitor. A revisão gráfica continua
independente: resultados negativos de arte da revisão atual ainda são
reutilizados, evitando releituras sem benefício.

Na mesma revisão, mídia, tamanho, data de modificação e assinatura de
manifesto de efeitos, o perfil é reutilizado sem ler nem recalcular o hash da
imagem. Perfil ausente ou incompatível com o SHA invalida esse cache. O
monitor usa a mesma verificação para não ignorar uma mídia apenas porque
seu tamanho e data não mudaram desde a versão anterior.

Reanálises mantêm as regras anteriores de preservação de receitas e aprovação
para o mesmo SHA: somente confirmações manuais e receitas com proveniência
estrutural correspondente sobrevivem, e somente se as cartas continuarem
validadas. A revisão não transfere dados de outra ISO nem promove hipóteses.
