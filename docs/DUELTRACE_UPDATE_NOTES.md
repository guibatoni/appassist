# DUELTRACE v0.16.0 — Preview

## Novidades
- Novo design HD da carta gerado automaticamente mesmo quando o cache antigo não existe.
- Extração automática de nomes de tipos por tabela textual encontrada no executável da ISO.
- Detecção de nomes substituídos por mod, incluindo GOD no lugar de Réptil quando houver tabela comprovável.

## Melhorias
- Biblioteca, Fusões, Drops, Mão e detalhes priorizam sempre a carta completa HD.
- O backend associa nomes de tipos ao SHA-256 da ISO selecionada sem configuração manual.
- Layout das cartas com nome, atributo, estrelas, arte, descrição e ATK/DEF dentro da moldura.

## Correções
- O servidor local regenera imagens antigas ou incompatíveis antes de exibi-las.
- Strings isoladas como GOD não são confundidas com tabelas completas de tipos.
- O scanner rejeita mapeamentos ambíguos e mantém nomes desconhecidos sem inventar dados.
