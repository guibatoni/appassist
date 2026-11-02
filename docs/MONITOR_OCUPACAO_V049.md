# DUELTRACE v0.4.9 — Monitor experimental de ocupacao de slots

Objetivo: distinguir o ID persistente de ultima carta (ex.: #010 em 0xBFF510
apos destruicao pelo oponente) de um possivel indicador de slot ocupado.

Os dados seguem como HIPOTESES. Nenhum endereco e validado como campo,
nenhuma fusao mao+campo e habilitada e nenhum byte da RAM e escrito.

## Capturas por fase (observacao visual do jogador)
1. ANTES: carta na mao e slot selecionado VAZIO.
2. PREPARADA (opcional): selecionada FaceUp/FaceDown e Guardian Star,
   ainda antes de setar a carta.
3. NA MESA: carta fisicamente no slot, antes de mudar o turno.
4. OCUPADA (controle opcional): mesmo monstro ainda no slot, sem outras acoes.
5. REMOVIDA: monstro destruido/retirado, slot visualmente VAZIO.
6. VAZIA (controle opcional): mesmo slot permanece vazio, sem novas acoes.
7. MAO ATUALIZADA (opcional): quando a RAM da mao mudar no turno; pode
   ocorrer antes ou depois da remocao, pois e um evento independente.

Cada captura e feita no mesmo PID e com o mesmo hash de perfil selecionado
manualmente (o emulador nao valida esse hash). A mao conhecida de cinco
registros em 0xBFF484 continua sendo apenas a referencia de leitura.

## Campo occupancy_analysis no JSON
- Detecta bytes onde ANTES != NA MESA e NA MESA != REMOVIDA.
- Favorce bytes que retornam ao valor inicial apos a remocao.
- Exclui offsets da estrutura confirmada da mao.
- Se houver controle OCUPADA/VAZIA, descarta offsets inconsistentes entre
  o mesmo estado visual.
- Marca bytes que ja haviam mudado em PREPARADA e reduz sua prioridade.
- Faz priorizacao de proximidade aos registros HIPOTETICOS de 28 bytes.
- Exporta no maximo 100 candidatos em cada JSON, somente enderecos, tres
  valores de um byte e metadados. Nunca exporta blocos brutos da RAM.
- Nao interpreta efeitos do duelo como prova de cartas nem valida slots.

## Escopo de leitura
Na interface, 96 KiB por padrao, como antes. O jogador pode habilitar
1 MiB de escopo experimental (0xB40000 a 0xC40000, ultimo byte excluido)
antes de iniciar o teste. E sempre somente leitura, apenas processo ePSXe,
sem varredura de toda a memoria e sem garantias de cobrir slots.

## Falsos positivos e controles
Uma batalha/mudanca de turno pode modificar centenas de bytes, incluindo
LP, efeitos, animacoes e registro historico. Portanto uma transicao que
retorna a zero nao prova ocupacao. Repetir com cartas diferentes no mesmo
slot, e a mesma carta em slots diferentes, mais controle selecionar/cancelar.
Se REMOVIDA for capturada apos outras acoes, a analise pode gerar muitos
falsos positivos. As etapas OCUPADA e VAZIA sao importantes para filtragem.

## Arquivos envolvidos
- scanner/field_occupancy_probe.py: analise read-only
- scanner/field_ram_probe.py: integra novas capturas e JSON
- scanner/biblioteca_mods.py: GUI de controle
- tests/test_field_occupancy_probe.py: testes de reversao, volatilidade,
  exclusao de mao, ordem das capturas e proibicao de escrita

## Referencia
Na v0.4.8, carta #010 no slot 1: o valor de 0xBFF510 mudou de #016 para
#010 ao setar e permaneceu #010 depois da destruicao pelo oponente.
Por isso a leitura de ocupacao deve ser separada da leitura do ID.
