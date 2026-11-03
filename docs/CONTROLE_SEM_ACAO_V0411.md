# DUELTRACE v0.4.11 — Protocolo SEM AÇÃO

## Correção do fluxo do jogo

O jogador confirmou que em Yu-Gi-Oh! Forbidden Memories a seleção de FaceUp ou FaceDown é um ponto sem retorno. Portanto, o procedimento da v0.4.10 que exigia PREPARADA → CANCELADA não é praticável nesse estágio da jogada e **não deve ser utilizado**.

A v0.4.11 remove o botão CANCELADA da interface e disponibiliza o controle negativo **2X. SEM AÇÃO (slot vazio)**. O antigo método interno permanece somente para compatibilidade com testes/código já existente; não representa o protocolo recomendado e não é apresentado na interface.

## Experimento de controle negativo: sem qualquer jogada

1. Abra a aba Campo de duelo; preencha o ID da carta que está na mão e o slot visualmente vazio.
2. Selecione Monitor direcionado. A opção de 1 MiB é opcional; com 96 KiB o monitor acrescenta apenas um bloco de 4 KiB para os candidatos em C39000.
3. Clique **1. ANTES**.
4. Sem selecionar cartas, orientar FaceUp/FaceDown, passar turno, atacar, abrir outros menus do jogo ou colocar cartas, clique **2X. SEM AÇÃO**.
5. Envie o arquivo gerado cujo nome termina em _SEM_ACAO_<timestamp>.json.

Essa captura encerra a sessão. Clique 1. ANTES novamente antes do experimento de invocação real.

O objetivo é medir **volatilidade espontânea**: quais bytes mudam mesmo sem interação. Este controle não testa nem presume que a invocação tenha sido cancelada.

## Experimento de invocação real: sessão independente

1. Comece com o mesmo slot vazio e, se possível, a mesma carta na mão. Clique 1. ANTES.
2. Se puder capturar a preparação com segurança antes da confirmação final, use 2. PREPARADA. Não tente cancelar a jogada após FaceUp/FaceDown.
3. Ao colocar efetivamente a carta no campo, clique 3. NA MESA.
4. Registre 4. OCUPADA (controle), 5. REMOVIDA quando ela realmente sair da mesa, e 6. VAZIA (controle). MÃO ATUALIZADA é opcional.
5. Envie o arquivo normal para comparação.

O jogo decide quando passa do estado de seleção à carta no campo. O Assistente não verifica esse momento automaticamente: a descrição de cada fase é fornecida visualmente pelo jogador.

## Saídas e limitações

- **CONTROLE_SEM_ACAO_CAMPO_RAM**: before, after_no_action, no_action_analysis, hypothetical_slot_probe e targeted_ram_monitor quando habilitado.
- **DIAGNOSTICO_CAMPO_RAM**: funcionamento anterior para invocação real, sem alterações nas validações.
- O controle SEM AÇÃO não permite PREPARADA/NA MESA posteriormente na mesma sessão. Reinicie por ANTES.
- Os candidatos 0xBFF510, 0xBFF52C, 0xBFF6B3 e 0xC39000–0xC39400 continuam NÃO VALIDADOS; não são posições, ocupação ou cartas confirmadas.
- O leitor continua somente leitura e restrito a 96 KiB (+4 KiB direcionados quando habilitado) ou 1 MiB. Nenhum dump bruto da RAM é salvo.
- Nenhuma escrita em RAM, ISO, ROM, saves ou memory cards. Nenhuma fusão envolvendo cartas no campo é habilitada.

A correção resolve uma incompatibilidade no protocolo experimental; **não significa que os slots da mesa tenham sido mapeados**.
