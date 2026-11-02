# Hipotese de registros de 28 bytes - Yu-Gi-Oh ePSXe (v0.4.8)

Arquivo real recebido: 20261102_225810_1793660290348398500.json.
Carta #065, FaceUp, slot 2 informado na interface (a posicao fisica nao foi lida da RAM).
ANTES, PREPARADA e NA MESA: mao [10,461,65,159,65].
DEPOIS DA ATUALIZACAO: mao [10,461,159,65,200].
REMOVIDA ocorreu antes de MAO ATUALIZADA, como mostram os timestamps.

ANTES -> PREPARADA: 20 bytes alterados na janela experimental de 96 KiB.
PREPARADA -> NA MESA: 0 bytes alterados.
NA MESA -> REMOVIDA: 678 bytes alterados.
NA MESA -> MAO ATUALIZADA: 688 bytes alterados.

Experimentos no slot 1 mudaram offsets em torno de 0xBFF504-0xBFF51B.
O experimento informado como slot 2 mudou offsets em torno de 0xBFF520-0xBFF537.
Separacao: 0x1C = 28 bytes. Isso sugere registros de passo 28, mas NAO os valida.

Agora o relatorio identifica valores uint16 LE em cinco enderecos hipoteticos:
- Slot 1: 0xBFF510
- Slot 2: 0xBFF52C
- Slot 3: 0xBFF548
- Slot 4: 0xBFF564
- Slot 5: 0xBFF580

Os valores sao coletados dos mesmos blocos de RAM ja lidos em cada fase.
O campo hypothetical_slot_probe exporta somente cinco valores uint16 por fase.
Um ID plausivel NAO prova carta em campo nem identifica ocupacao, lado ou status.
Todos os indicadores de validacao continuam falsos; fusoes mao+campo desativadas.
Nenhum dump bruto e exportado; a leitura expandida opcional de 1 MiB
permanece DESLIGADA por padrao e fora da interface desta versao.

Proximos testes: slot fisico 2 confirmado pelo usuario, mesmo ID em outro slot,
selecionar e cancelar sem colocar carta, remocao separada de passar turno,
e nova carta no mesmo slot; repetir em outro duelo e confirmar ocupacao.
Se os cinco valores nao forem IDs consistentes por posicao, descartar hipotese.
