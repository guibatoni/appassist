# DUELTRACE v0.4.12 — Dois candidatos prioritários sob controle

## Evidência de origem

No teste de invocação real da carta #291 no slot físico 1, confirmado visualmente pelo jogador, os bytes candidatos apresentaram as sequências:

| Endereço | ANTES | PREPARADA | NA MESA | OCUPADA | REMOVIDA | VAZIA |
|---|---:|---:|---:|---:|---:|---:|
| 0xC393FA | 65 | 65 | 63 | 63 | 65 | 65 |
| 0xC39822 | 30 | 30 | 31 | 31 | 30 | 30 |

Isso é apenas correlação entre capturas, NÃO valida um indicador de ocupação. A região experimental 0xC39000 contém muitos bytes voláteis; controles SEM AÇÃO anteriores demonstraram alterações espontâneas em centenas de bytes mesmo sem jogada.

Os controles anteriores não registraram valores pontuais nesses dois endereços; precisamos de um novo diagnóstico SEM AÇÃO já na v0.4.12.

## Novidades

- Adição de 0xC393FA e 0xC39822 ao monitor de valores uint8 em cada fase da captura.
- Expansão da faixa resumida de diferenças para 0xC39000..0xC399FF (2,5 KiB), dentro do mesmo bloco lido de 4 KiB. NÃO há aumento adicional de RAM lida.
- Campo `priority_address_review` nos dois tipos de JSON:
  - `CONTROLE_SEM_ACAO_CAMPO_RAM`: compara ANTES e SEM AÇÃO e aponta ESTAVEL_SEM_ACAO ou MUDOU_SEM_ACAO. Dados ilegíveis geram LEITURA_INCOMPLETA.
  - `DIAGNOSTICO_CAMPO_RAM`: compara ANTES, PREPARADA, NA MESA, OCUPADA, REMOVIDA e VAZIA. Sinaliza falta de controles, mudança na preparação, instabilidade em OCUPADA/VAZIA, persistência ou reversão.
- A Biblioteca de Mods exibe o estado de cada candidato após SEM AÇÃO ou VAZIA. Nenhum status é aprovação de slot.

## Experimento 1 — SEM AÇÃO (primeiro a executar)

1. Instale o patch v0.4.12.
2. Abra Biblioteca de Mods → Campo de duelo. Habilite Monitor direcionado. A opção 96 KiB já inclui um bloco extra de 4 KiB em 0xC39000; **1 MiB é opcional**, não necessário para os dois endereços.
3. Com a carta #291 na mão e o slot 1 vazio, clique 1. ANTES.
4. Sem tocar em nenhuma ação ou menu do jogo, clique 2X. SEM AÇÃO.
5. Envie o novo JSON cujo nome contém `_SEM_ACAO_`.

A captura NEGATIVA termina aí: sem PREPARADA, FaceUp/Down, NA MESA, cancelamento ou remoção.

## Experimento 2 — invocação real (sessão independente)

Se disponível, use a mesma carta #291 no slot físico 1, inicialmente vazio. Faça as etapas ANTES, PREPARADA (opcional), NA MESA, OCUPADA, REMOVIDA após a carta sair fisicamente e VAZIA. Só marque PREPARADA se ela realmente estiver nessa situação; não tente cancelar FaceUp/Down.

Repetir em outro slot e com outra carta deve ocorrer apenas depois de analisarmos os dois experimentos.

## Segurança

Todos os endereços são HIPÓTESES. O processo ePSXe é lido sem escrita de memória; não há dump de blocos brutos no JSON. O hash da ROM continua selecionado manualmente e não comprova que a ISO ativa foi verificada. Não escrevemos ISO, ROM, saves nem memory cards. Leitura de cartas no campo e fusões mão + campo permanecem desativadas.
