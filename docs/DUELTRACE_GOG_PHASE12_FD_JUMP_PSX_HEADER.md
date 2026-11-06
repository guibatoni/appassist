# DUELTRACE — Etapa 12: 0xFD como redirecionamento de texto e diagnóstico PS-X EXE

## Evidência real coletada — GOG MOD 2.2, revisão 25

- 722 cartas extraídas estruturalmente, IDs ainda não confirmados em jogo.
- 39 adversários candidatos, 0 publicados; 39 ponteiros únicos.
- Melhor janela: 38 dos 39 registros contêm `0xFF` em seus bytes.
- 22 contêm `0xFD` antes de `0xFF`, e têm glifos legíveis depois de `0xFD`.
- 6 registros contêm dados não nulos após o primeiro `0xFF`.
- 1 registro tem limites incompletos na primeira janela.
- Sondas de layout deslocado: nenhum candidato.
- MIPS: `psx_header_invalido`, sem referências verificadas.

### Referência técnica externa importante

A análise pública do executável varejo do jogo **confirma** que a sequência
`FD lo hi` é despachada para `Text_SetCursorOffset`, que substitui
os 16 bits baixos do cursor de texto por um endereço little-endian,
preservando o banco de 64 KiB atual. Por exemplo, `FD 1C 13` redireciona
para o offset `0x131C` do banco original.

Fonte: [Yu-Gi-Oh! Forbidden Memories Recompiled — Modding Tutorial Evidence]
(https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/notes/modding-tutorial-evidence.md).

O mesmo motor utiliza `0xFF` como fim de string, `0xFE` como nova linha,
`0xF8` para comandos estendidos. **Isso é comportamento do jogo
original**. O GOG MOD 2.2 pode ter substituído rotinas ou dados.
Portanto, por enquanto a sequência `FD lo hi` é uma hipótese informada,
não uma confirmação dos IDs de adversários deste mod.

### Outro resultado de pesquisa

`PS-X EXE` normalmente possui cabeçalho de 0x800 bytes com ponto de
entrada, endereço de carga e tamanho do payload nos offsets 0x10/0x18/0x1C.
O scanner de MIPS rejeitava o GOG sem explicar qual campo falhara.
Fonte: [psx-spx — Executables]
(https://psx-spx.consoledev.net/dev/ps1/cdr/cdromfileformats/executables/).

## Implementado — scanner revisão 26

- Novo `scanner/dueltrace_fd_jump_probe.py`: para cada uma de no máximo
  cinco janelas, observa até 39 registros e 96 bytes por registro.
- Quando encontra `0xFD` **antes** do `0xFF` dentro do próprio registro,
  confere se existem dois bytes de argumento e interpreta
  `low | high << 8` como alvo **hipotético** do mesmo banco de texto
  de 64 KiB.
- Contabiliza alvos dentro/fora do banco, destino que contém `0xFF`,
  destinos que começam com `FD`, `F8` ou `FF`, alvos repetidos,
  saltos para o próprio registro e quantidade de alvos distintos.
- **Não segue execução MIPS, não reconstrói nomes, não altera IDs e não
  publica adversários.** Tais resultados são contagens diagnósticas.
- `dueltrace_mips_reference_probe.py` preserva os motivos específicos
  de rejeição do cabeçalho: assinatura ausente, payload truncado,
  destino RAM inválido, PC fora do payload e coerência.
- `numeric_evidence`, API da Biblioteca e
  `Copiar diagnóstico técnico` passam a exportar somente essas métricas,
  com whitelist, no **schema 4**. Nenhum dado bruto da ISO, hash,
  nome, caminho, endereço ou sequência de bytes é copiado.
- `SCAN_PARSER_REVISION=26` força reanálise automática do perfil por SHA.

## Testes automáticos

Fixtures sintéticas, sem ROM, exercitam:
- FD seguido de dois bytes de offset e alvo no mesmo banco contendo FF.
- Não promoção de adversário mesmo quando o salto é plausível.
- Rejeição de ponteiros ausentes e executáveis inválidos.
- Separação de cabeçalho coerente, assinatura ausente e payload
  declarado incompatível.
- Sanitização de dados e compatibilidade do botão de copiar.
- Regressões do parser anterior, fusões, drops, RANK e build Windows.

**A suite automatizada não substitui a validação no GOG real.**

## Próximo passo

1. Instalar a Preview desta revisão **apenas depois de CI aprovada**.
2. Clicar em **Atualizar dados** na Biblioteca, no GOG MOD 2.2.
3. Clicar em **Copiar diagnóstico técnico** e compartilhar o JSON schema 4.
4. Examinar `fdJumpWindows[0]`, especialmente
   `fdWithTwoArguments`, `jumpTargetInBank`,
   `jumpTargetHasFF`, `jumpTargetDistinctCount`.
5. Examinar `alternativeLayoutSearch.mipsStaticReferences.headerEvidence`
   para verificar qual requisito PS-X EXE falhou.
6. Se os destinos FD forem coerentes, comparar nomes/IDs e transições
   de texto no emulador com observações diretas; sem validar, não
   inferir que 39 personagens foram identificados.
7. As 117 matrizes de drops e as regras de RANK continuam independentes;
   fusões também requerem sua própria extração.

Não mesclar automaticamente à `main`; preservar o perfil e a ISO.
