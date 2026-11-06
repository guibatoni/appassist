# DUELTRACE — Etapa 15: detector de famílias de matrizes MultiMod

**Data:** 2026-11-06 · **Origem:** imagem de disco enviada pelo próprio usuário · **Finalidade:** perícia estrutural, sem extração de conteúdo protegido para GitHub.

## Evidência REAL, reproduzida na ISO GOG MOD 2.2

- Disco PS1 RAW 2352/Mode2, `SYSTEM.CNF` aponta para `GOG_VNT.223`.
- Contêiner analisado: `G0SD/GOG_SD1.23` (38.148.608 bytes).
- Encontrada a região de **40 blocos completos consecutivos**, cada bloco com 0x1800 bytes.
- Bloco inicial em **0xE99800** e último em **0xED4000**. A série anterior da Etapa 14 começava em 0xE9B000, isto é, **um bloco depois do início real da sequência estrutural**.
- **40 matrizes candidatas de deck e 120 de distribuição**, todas com 722 valores u16 normalizados para 2.048, no formato de pesos simples, agrupadas em quatro matrizes por bloco.
- Espaçamento de matrizes 0x5B4, passo de blocos 0x1800.
- Os **40 trechos de 200 bytes** após as quatro matrizes são iguais entre si; os **40 finais de 104 bytes** são `FF` repetido. A posição de rank rules é estruturalmente compatível com a família FM clássica.
- Existem **duas janelas contíguas de 39 blocos**: base 0xE99800 e base 0xE9B000. A mera soma das tabelas não determina qual janela corresponde aos 39 nomes já localizados no executável.
- Outros três grandes recursos do disco foram inspecionados e não tiveram uma família 39×4 reconhecida nas hipóteses testadas.

**Importante:** a presença de 40 blocos não estabelece 40 adversários jogáveis. Identidade dos 39 nomes, índice em tempo de execução, grupo RANK e comportamento MIPS ainda precisam de validação independente. Nenhum drop ou RANK foi desbloqueado.

**Corroboração independente (formato original):** [Yu-Gi-Oh-Forbidden-Memories-Recompiled — duel package negative-space audit](https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/notes/duel-package-unused-data.md). A fonte documenta 40 blocos indexados de 0x1800 bytes, quatro regiões de 0x5B4, 0xC8 bytes de regras de rank e 0x68 bytes de preenchimento. A compatibilidade do **mod GOG** com a *interpretação de cada campo* não é afirmada por essa comparação.

## Implementação nova (sem alterar o jogo)

`scanner/dueltrace_mod_family_probe.py` — módulo de varredura de conteúdo com regras reutilizáveis:

- localiza janelas por conteúdo (soma de pesos) e não pelo nome `WA_MRG.MRG`;
- testa matrizes `plain`, `x15_masked`, `plain_deck_masked_drops`;
- suporta famílias de passos/strides adicionadas via configuração;
- confere 156 matrizes por janela e procura os limites físicos antes/depois;
- agrupa janelas sobrepostas em séries de 39, 40 ou mais blocos;
- confere, quando presente, a assinatura estrutural das regras e da cauda `FF`;
- preserva estado **não verificado em jogo** e impede liberar RANK ou drops por heurística;
- não retorna nomes, IDs de cartas, pesos individuais, textos ou bytes proprietários.

`scanner/dueltrace_mod_probe_cli.py` — perícia read-only de mídia local que reutiliza `scanner_multiiso.Disc`, analisa até quatro recursos (128 MiB de orçamento) e emite um JSON agregado. Não tenta converter toda ISO em compatibilidade completa.

`tests/test_dueltrace_mod_family_probe.py` — 11 testes sintéticos, todos passaram localmente. A bateria completa do repositório e a compilação Windows ainda precisam da CI na branch que receber este trabalho.

## Como executar pela linha de comando

No repositório DUELTRACE, com Python >=3.10:

```powershell
python scanner/dueltrace_mod_probe_cli.py --iso "C:\Games\GOG MOD 2.2 - Drop 15 (NDC).iso" --output "auditoria_multimod.json"
```

Não precisa copiar o jogo para o repositório. Nunca adicione ISOs, ROMs, saves privados ou conteúdos extraídos ao GitHub. O JSON gerado contém apenas informações estruturais e hashes abreviados dos recursos.

## Limites explícitos

- Alinhamentos de início não múltiplos de 2.048 bytes precisam de dicas de um adaptador; essa preferência evita falsos positivos onde zeros permitem janelas deslocadas.
- Famílias que comprimem dados, mudam o número de cartas, alteram a fórmula de pesos ou guardam blocos em outra estrutura exigem novos decodificadores, com provas sintéticas e reais.
- Não existe garantia técnica de reconhecer **todo e qualquer mod** automaticamente somente com uma ISO; o motor é extensível e falha de maneira segura quando desconhece o formato.
- A identidade de adversários e os resultados de RANK exigem prova de execução (RAM/MIPS/log do duelo), não apenas tabelas que somam 2.048.

## Próxima etapa de engenharia

1. Validar no Windows a mudança da revisão do scanner e o relatório estrutural `single_family_unmapped_windows`.
2. Rastrear referência do índice em execução para decidir se o bloco inicial é reservado e se os 39 nomes associam-se aos blocos 1–39 (hipótese, não fato para o GOG).
3. Confirmar grupos através da rotina de recompensa e registros reais de vitória, antes de publicar cartas ou RANK.
4. Construir adaptadores por **assinatura de família**, não por nome de ISO, e adicionar mais ISOs com estruturas realmente distintas à suíte de compatibilidade.
5. Manter PR em draft até testes Windows/ePSXe; não fazer merge na main automaticamente.