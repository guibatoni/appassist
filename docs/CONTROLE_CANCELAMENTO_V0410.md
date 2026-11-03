# DUELTRACE v0.4.10 — Controle negativo da preparação

## Motivo

Nos testes anteriores, o ID da carta apareceu nos registros hipotéticos de passo 28 (0xBFF510 para o slot 1 e 0xBFF52C para o slot 2), antes mesmo de colocar a carta na mesa. E persistiu após sua destruição. Não confirma ocupação. Outros candidatos surgiram em 0xC39000–0xC39400, mas também podem refletir interface, animação ou combate.

## Experimento A: nenhuma invocação (controle negativo)

1. Escolha uma carta de ID conhecido e confirme que o slot selecionado está vazio.
2. Deixe o Monitor direcionado ligado. Com varredura de 96 KiB, ele acrescenta um bloco de 4 KiB em 0xC39000. Com 1 MiB a região já está incluída.
3. Clique 1. ANTES.
4. Selecione carta, FaceUp/FaceDown e Guardian Star sem colocá-la na mesa; clique 2. PREPARADA.
5. CANCELE a seleção no próprio jogo antes de entrar no slot. Confirme que a carta nunca chegou fisicamente à mesa.
6. Clique 3X. CANCELADA — sem invocar.
7. Compartilhe o JSON separado com nome contendo _CANCELADA_.

Esse botão ENCERra a sessão. Para testar invocação real, recomece em 1. ANTES.

NÃO clique REMOVIDA se a carta nunca foi colocada no campo. NÃO marque CANCELADA se chegou a colocá-la no slot.

## Experimento B: invocação real em nova sessão

Com a mesma carta e slot (se possível), use 1. ANTES, 2. PREPARADA, 3. NA MESA, 4. OCUPADA, 5. REMOVIDA, 6. VAZIA; 7. MÃO ATUALIZADA é opcional. Envie o JSON resultante para comparar com o cancelamento.

## Arquivos e dados

- scanner/field_cancel_probe.py: comparação de três estados, somente leitura.
- scanner/field_ram_probe.py: fase de cancelamento, resumo pontual das regiões, arquivo próprio.
- scanner/biblioteca_mods.py: botão CANCELADA e opção monitor direcionado.
- tests/test_field_cancel_probe.py: testes de segurança, ordem de captura e controle negativo.

O arquivo cancelado usa type=CONTROLE_CANCELAMENTO_CAMPO_RAM e inclui before, after_preparation, after_cancellation, negative_control_analysis, hypothetical_slot_probe, targeted_ram_monitor. NUNCA registra after_summon como carta colocada. O arquivo de invocação mantém o schema=2, com targeted_ram_monitor opcional.

## Categorias observacionais

- restored_after_cancel: alterou em PREPARADA e retornou ao valor original.
- persisted_after_cancel: alterou em PREPARADA e permaneceu após cancelar.
- different_after_cancel: alterou e passou a um terceiro valor.
- changed_only_on_cancel: permaneceu até PREPARADA, alterando somente depois.
- focus_before_to_prepared, focus_prepared_to_cancelled, focus_before_to_cancelled: diferenças da faixa 0xC39000–0xC39400 com até 64 amostras por transição.

Endereços monitorados incluem 0xBFF510, 0xBFF52C, 0xBFF548, 0xBFF564, 0xBFF580, 0xBFF6B3 e candidatos anteriores entre 0xC38F80–0xC393D1. Nenhum está validado como campo.

## Limites importantes

A captura depende de confirmação visual do usuário. O SHA do perfil da ISO é selecionado manualmente, não verificado automaticamente no ePSXe. Nem o retorno de um byte ao valor anterior nem um ID plausível provam ocupação. Não fazemos dump bruto de RAM, nem escrita na memória, ISO, ROM, save ou memory card. Fusões mão + campo continuam desativadas.
