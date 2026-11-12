# DUELTRACE v0.15.0 — Preview

## Novidades
- Análise automática de tipos ao importar ou atualizar dados de cada ISO.
- Tipos personalizados, códigos 24–31 e possíveis alterações passam a ser identificados para revisão.
- Relatório local tipos_iso.json com códigos, quantidades e evidências específicas do mod.

## Melhorias
- Biblioteca, Fusões, Drops e Mão utilizam classificações ligadas à ISO selecionada.
- ATK/DEF reais continuam visíveis nas cartas com atributos de monstro.
- O scanner atualiza o perfil de tipos por ISO e regenera caches derivados.

## Correções
- Cartas suspeitas deixam de receber nomes de tipos do original sem confirmação.
- Molduras de cartas não são atribuídas a tipos desconhecidos sem evidência.
- Nenhuma ISO original é alterada; relatório e identificação permanecem ligados ao SHA-256.
