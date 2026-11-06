# DUELTRACE — Fase 11: controles 0xFD/0xFF e sondagem MIPS sem layout alternativo

## Evidência real fornecida pelo usuário (scanner 24)

ISO: `GOG MOD 2.2 - Drop 15 (NDC).iso`.

- Cartas: **722 estruturalmente extraídas** (IDs não confirmados em jogo).
- Adversários disponíveis: **0**; nomes candidatos: **39**, ainda não publicados.
- Cada janela do relatório exibe 39 ponteiros distintos, **sem aliases**.
- Melhor janela: `terminatedFF=16`, `glifo_invalido=22`,
  `sem_ff_antes_proximo=1`; `firstInvalidByteHistogram=0xFD:22`.
- Existem **38 limites físicos alcançados** na melhor janela e
  **2 inversões** de ordem ordinal. Os intervalos ordinais chegam a
  -3742/+3651; não significam limites físicos negativos.
- `boundaryDecision=dados_apos_marcador`: o primeiro código inválido
  não é seguido apenas de preenchimento zero até o próximo registro.
- As sondas `namePointer` e `relocatedNames` encontraram **0 layouts**.
- `mipsStaticReferences=indisponivel` na revisão 24 porque o scanner
  executava a análise de referências **somente quando outras sondas
  identificavam offsets candidatos**. Esse estado não comprova ausência
  de referências MIPS.

### Interpretação conservadora

O byte `0xFD` pode ser código de controle inline, terminador diferente,
parte de codificação modificada ou dado inválido. Sua frequência
não comprova nenhuma dessas hipóteses. Há 16 registros com `0xFF`,
22 parados por `0xFD` e um sem `0xFF` antes da fronteira.
Não publicar nomes, não converter `0xFD` em `0xFF` automaticamente,
não renumerar IDs e não importar adversários de outro mod.

## Alterações — parser revisão 25

- Novo `scanner/dueltrace_opponent_control_probe.py`, somente leitura:
  examina **até 5 janelas de 39 registros**, com no máximo 96 bytes
  por registro, sempre respeitando os limites físicos já medidos.
- Distingue `0xFD` com `0xFF` posterior, `0xFD` sem `0xFF`,
  glifos legíveis imediatamente após `0xFD`, bytes de controle
  posteriores, conteúdo não nulo após `0xFF` e limites truncados.
- Registra apenas histogramas de **códigos de controle** e contagens,
  sem texto, ROM, offsets ou caminhos.
- A saída agregada fica em
  `independent_opponent_discovery.forensicEvidence.controlWindows`.
- O botão **Copiar diagnóstico técnico** passa ao schema 3 e inclui
  `controlFlowWindows` com campos explicitamente permitidos.
- Quando sondas clássicas de layout não encontram nenhum endereço,
  o scanner agora investiga **até 4 bases de tabelas candidatas já
  observadas**, via `inspect_mips_table_references`, sem tentar
  adivinhar endereços.
- A saída de MIPS diferencia `sem_alvos_candidatos`,
  `sem_evidencia`, `psx_header_invalido`,
  `referencias_mips_candidatas` etc. Referência estática não é prova
  de execução e nunca habilita nome, drop ou RANK.
- A revisão 25 força nova análise de ISOs cacheadas pelo SHA.

## Testes

`tests/test_dueltrace_opponent_control_probe.py` simula 39 ponteiros
únicos e uma mistura artificial de 16 terminadores `0xFF`,
22 primeiros códigos `0xFD` e 1 registro sem `0xFF`.
Inclui casos com `0xFD` seguido de glifo+FF, conteúdo extra após
FF, executável truncado e filtro de privacidade.

As verificações sintéticas não garantem reconhecimento da ISO real.

## Próxima ação no Windows

1. Instalar a Preview **somente após CI final aprovada**.
2. Expandir o GOG MOD 2.2, clicar **Atualizar dados** e depois
   **Copiar diagnóstico técnico**.
3. Compartilhar o novo JSON, especialmente:
   - `controlFlowWindows[0]`:
     `fdBeforeFf`, `fdFollowedByGlyph`, `fdWithoutFf`,
     `nonZeroAfterFf`, `nonZeroAfterFd`;
   - `alternativeLayoutSearch.mipsStaticReferences.state` e
     `candidateCount`.
4. Caso o formato continue sem identificação, analisar o
   `relatorio.json` local e fazer sondagem MIPS controlada com
   Ghidra/Capstone e observações de oponentes no emulador.
5. Só após confirmação dos IDs em jogo cruzar os adversários com as
   117 matrizes de drops e os grupos específicos do mod; fusões exigem
   investigação separada.

Nenhuma ISO, executável proprietário, Memory Card ou dado pessoal
é enviado ao modelo local. Tudo fica isolado na branch e na PR,
sem merge automático na `main`.
