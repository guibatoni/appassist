# Forbidden Memories MultiMod v0.4.6 — Investigação controlada do campo

## Origem da hipótese
A gravação temporal real da v0.4.5 registrou 148 amostras e 37 transições.
O usuário confirmou que invocou a carta #291 na primeira ação; na mão
`[159,291,16,635,192]` o #291 sumiu e surgiu o #010 por volta de 13,62 s.
O desaparecimento na mão NÃO demonstra, por si, a localização da carta na mesa.

## Novo diagnóstico de três estados
Biblioteca de Mods > aba **Campo de duelo**:

1. No duelo com a carta conhecida **na mão**, ainda **ausente da mesa**,
   selecione sua ISO ativa, escreva o ID (exemplo #291) e clique
   **1. Capturar ANTES**. Confirme visualmente o estado.
2. No ePSXe, invoque **exatamente a carta indicada**; com ela visível no
   seu campo, clique **2. Capturar INVOCADA** e confirme visualmente.
3. Opcional: remova a carta do seu campo (por batalha ou outra ação normal)
   e clique **3. Capturar REMOVIDA**.

O relatório JSON fica em
`%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\diagnosticos_campo\<SHA da ISO>\`.
Envie o **JSON** à conversa. Não envie ROM, save ou Memory Card.

## Limites precisos
- Uma região HIPOTÉTICA de **96 KiB**, em **24 blocos de 4 KiB**,
  alinhada em torno do endereço conhecido da mão `0xBFF484`,
  é examinada em cada fase.
- Não é uma varredura completa do processo e não garante incluir
  estruturas da mesa. Região não legível é descartada.
- Padrão investigado: `uint16 little-endian` para o ID informado.
  São apenas **ocorrências candidatas**: o mesmo número pode existir
  em contadores, arrays não relacionados, ponteiros ou animação.
- Exclui a região conhecida da mão para reduzir falsos positivos,
  mas precisa de confirmação posterior com outros IDs e slots.
- Exige PID e SHA de perfil selecionado constantes, mão válida e
  redução do número de ocorrências do ID na mão após invocação.
- Armazena **endereços candidatos e contagens**, não exporta a área bruta
  da RAM. A captura opcional de remoção acrescenta dados ao mesmo JSON.
- Proteção: até 150 endereços candidatos são detalhados; contagem
  total informada, listas excedentes truncadas.
- **Não** liga o motor de sugestões mão + campo; não conhece slots
  nem lado da mesa e não marca cartas como verificadas.
- **Não** altera a RAM, ISO, executável do ePSXe, Memory Cards ou saves.

## Critérios de validação para versões futuras
- Repetir invocação/remoção do ID #291 em outro duelo.
- Comparar dois IDs de monstro em slots distintos (incluindo duplicatas).
- Comparar cartas da mão e campo de ambos os lados para separar
  o próprio campo do campo adversário.
- Testar invocação com carta de equipamento, carta virada e outras ações.
- O mesmo endereço deve corresponder a slot e lado estáveis e ser
  reproduzível após reiniciar o ePSXe.
- Somente habilitar sugestões de fusões com cartas do campo após
  validar esses campos independentemente e verificar a mecânica de fusão.
- Se nenhum ID novo for encontrado, considerar que o campo está fora
  da faixa experimental e **não ampliar automaticamente** o escaneamento.

## Testes
- Leitor simulado com PID/ISO constante e mão validada.
- ID surge no bloco após invocação e desaparece após remoção.
- Exclusão da mão, falha parcial de blocos, rejeição de ID inválido,
  recusa quando carta não saiu da mão, PID/ISO trocado.
- CI não substitui validação no ePSXe real.
