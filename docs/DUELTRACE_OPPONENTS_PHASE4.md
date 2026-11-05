# DUELTRACE — Etapa 4: Oponentes independentes no GOG MOD 2.2

## Evidência observada

Em 05/11/2026, a Biblioteca de Mods mostrou 722 cartas extraídas da
`GOG MOD 2.2 - Drop 15 (NDC).iso`, mas nenhum oponente, fusão ou drop.
Esse resultado é evidência de que a etapa de **cartas** funcionou para
esta instalação; não comprova a identidade dos 722 IDs em jogo.

## O que implementamos na revisão 18

`dueltrace_independent_opponents.py` investiga tabelas de ponteiros de
adversários **no mesmo executável selecionado pela ISO** sem depender
de nomes completos de cartas e sem copiar dados de outro mod.

- Limite de leitura: índices 723–1190, 39 nomes consecutivos, máximo
  de 8 hipóteses compactas.
- Leitura de registros terminados por 0xFF respeitando a próxima
  fronteira física conhecida; impede consumir bytes do registro seguinte.
- Cada janela exige nomes plausíveis, diversidade de texto, ponteiros
  distintos e vizinhança não ocupada antes de ser escolhida.
- Se houver **uma única sequência isolada** de 39 nomes completos,
  ela pode ser exibida no perfil como
  `oponentes=extraidos_estruturalmente`.
- Caso haja várias sequências possíveis, o perfil NÃO incorpora nenhuma.
- Quando outro byte parece funcionar como terminador, a hipótese fica
  em quarentena: **não substituir automaticamente 0xFF**, não apagar
  sufixos como `v` e não inventar IDs.
- Metadados e hipóteses são armazenados no
  `relatorio.json` e `oponentes_candidatos_nao_verificados.json`.
- O motor avança `SCAN_PARSER_REVISION` para **18**, refazendo a
  análise de uma ISO após a atualização.

## Regras de publicação e RANK

Se nomes de adversários forem extraídos por posição e estrutura mas
a ordem de IDs não tiver sido comprovada em jogo, a aplicação pode
apresentar os nomes com um aviso de procedência. **Não associa os nomes
automaticamente às 117 matrizes de drops, às dez classes clássicas, nem
altera a fórmula de RANK**. O importador bloqueia especificamente a
promoção das matrizes e decks nesse estado.

O Remaster X15 continua usando apenas sua própria identidade de ISO.
Outros mods mantêm a classificação original (POW/TEC) quando o
mapeamento foi verificado, sem receber Z-POW por semelhança de tabela.

## Como testar no Windows

Após publicar e instalar a Preview aprovada:

1. Abra Biblioteca de Mods e o registro do GOG MOD 2.2.
2. Clique em **Atualizar dados** — usa a ISO local e refaz o scan
   porque a revisão do parser mudou.
3. Confira a linha **Oponentes**. Se aparecer **39**, leia o aviso:
   trata-se de extração estrutural, não confirmação de IDs em ePSXe.
4. Se aparecer traço, confira a informação sobre nomes candidatos.
5. Se a procura ainda falhar, extraia o diagnóstico da mesma imagem no
   diretório `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\analises\`,
   dentro da pasta específica da análise. O `relatorio.json` guarda
   `nomes_status`, `opponent_pointer_candidates`,
   `opponent_name_boundaries` e
   `independent_opponent_discovery`. Revise nomes/caminhos privados
   antes de compartilhar o relatório. Não compartilhe ISOs, memory
   cards, executáveis proprietários, tokens ou saves.

## Próxima frente, dependente de dados reais

Com os adversários estruturalmente identificados, comparar os 39 IDs com
adversários observados no emulador, localizar referências MIPS aos
ponteiros e validar a correspondência de cada grupo físico de drop.
Depois, validar a extração das fusões por bases de dados consistentes
da própria ISO. Sem o arquivo GOG ou seu relatório, nenhum resultado
numérico de drops/fusões pode ser afirmado.

## Testes

`tests/test_dueltrace_independent_opponents.py` usa executáveis
**sintéticos** e cobre posições deslocadas, layouts ambíguos,
terminadores diferentes, proteção de hashes e bloqueio de drops/RANK.
Os testes não demonstram compatibilidade em duelo real.
