# Correção de observação: posição real da carta #211 (02/11/2026)

## Confirmação do usuário
O experimento `20261102_225125_1793659885925603800.json`, carta **#211**,
trazia `observed_by_user.slot_position_1_to_5=2`.
**O usuário posteriormente corrigiu: a carta foi colocada fisicamente no slot 1.**

A captura do ID #200, arquivo `20261102_224909_1793659749152322200.json`,
também se refere ao slot 1.

Portanto, **NÃO existe ainda uma comparação experimental confirmada
entre slots 1 e 2**. É incorreto afirmar que 0xBFF510 acompanha cartas
independentemente da posição do campo, com base nesses dados.

## Evidências mantidas
- Para #200: ANTES→PREPARADA 19 bytes; PREPARADA→NA MESA 0 bytes.
- Para #211: ANTES→PREPARADA 22 bytes; PREPARADA→NA MESA 0 bytes.
- Em ambos a RAM da mão permaneceu sem atualização imediata.
- O endereço 0xBFF510 e a região próxima respondem a alterações de preparação,
  mas não identificamos nem validamos a semântica de slot ou ocupação.
- Nenhuma receita de fusão foi aprovada por esses diagnósticos.

## Próximo experimento correto
Capturar, em novo duelo, **UMA carta efetivamente colocada no slot 2**,
preenchendo seletor `2`. Capturar ANTES, PREPARADA opcional, NA MESA
antes de passar turno e REMOVIDA opcional. Confirmar visualmente cada fase
e a posição física, pois o seletor é apenas uma anotação.
Somente depois comparar slots 1 e 2.

## Código experimental não liberado
Há uma opção **desativada por padrão** de faixa ampliada de 1 MiB em
`scanner/field_ram_probe.py`, limitada a leituras `reader.read` e
sem dados brutos exportados. A UI da versão v0.4.7 continua na
faixa anterior de 96 KiB. **Não existe release novo** decorrente desta
correção. Nunca declarar descoberta/validação de endereço de mesa
sem evidências de slots distintos e controles.
