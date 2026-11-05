# DUELTRACE — Diagnóstico de 39 nomes candidatos (revisão 19)

## Evidência obtida na UI

A ISO `GOG MOD 2.2 - Drop 15 (NDC).iso` passou a fornecer **722 cartas**.
Na revisão 18, a interface mostrou **"Até 39 nomes de adversários
candidatos detectados (não verificados)"**, mas continuou com zero
adversários disponíveis. O número representa apenas a maior janela com
nomes estruturalmente plausíveis; não comprova 39 IDs.

## Correção de observabilidade

- O scanner diferencia várias situações de rejeição e fornece
  `reasonCode` e `reason`, na linguagem do aplicativo.
- O usuário vê uma explicação curta sob os candidatos de adversários.
- `oponentes_candidatos_nao_verificados.json` guarda, **somente localmente**,
  até três janelas de 39 registros, com ID candidato, prefixo legível,
  `recordStatus` e byte inválido. Esses dados não migram para
  `oponentes.csv` nem para os drops.
- O `relatorio.json` inclui apenas metadados agregados, sem os nomes
  candidatos nem bytes extraídos.
- A revisão do parser sobe de 18 para 19; `Atualizar dados` força uma
  nova análise da mesma ISO, vinculada por SHA-256.
- IDs não são remapeados com base em nome, similaridade, posição
  aproximada, ou sugestão da IA.

## Possíveis causas (nenhuma deve ser presumida antes do relatório)

| Código | Situação |
| --- | --- |
| `terminador_incompativel` | Prefixos legíveis, mas sem terminador 0xFF confirmado. O byte observado não é, por si só, prova de terminador alternativo. |
| `multiplos_blocos` | Mais de uma janela completa plausível; a ordem de IDs continua ambígua. |
| `bloco_nao_isolado` | Uma janela completa não tem limites independentes comprovados. |
| `ponteiros_repetidos` | Registros candidatos compartilham ponteiros. |
| `nomes_repetidos` | Baixa diversidade de nomes na janela. |
| `nomes_parciais` | Não existem 39 registros completos e distintos de forma inequívoca. |
| `layout_incompativel` | Tabelas de glifos/ponteiros são incompatíveis. |

## Como obter evidência real sem compartilhar a ISO

No Windows:

1. Feche o jogo para evitar que a ISO seja modificada durante a inspeção.
2. Na Biblioteca de Mods do DUELTRACE, clique em **Atualizar dados**.
3. Abra `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\analises`, procure a
   subpasta mais recente correspondente à ISO GOG e localize `relatorio.json`.
4. Revise o relatório para verificar possíveis nomes/caminhos locais e
   compartilhe-o **somente se desejar**. Não envie ISO, arquivos
   executáveis proprietários, saves, Memory Cards nem tokens.
5. Para investigação binária mais profunda, também há um
   `oponentes_candidatos_nao_verificados.json` na mesma análise. Esse arquivo
   pode incluir nomes extraídos do jogo; compartilhar é opcional.

O relatório permite identificar a causa específica da rejeição.
**Não existe garantia de reconhecer universalmente qualquer mod**.
Somente evidências independentes, inclusive leitura em jogo quando
necessária, podem confirmar IDs, fusões, drops e grupos de RANK.
