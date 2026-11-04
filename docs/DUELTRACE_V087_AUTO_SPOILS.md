# DUELTRACE v0.8.7 — Spoils automático, 101 pontos de abertura

Base: v0.8.6 (PR #36, commit `2ba44cc54489c58f8d57ba09c5c337a96fb69331`).  
Branch: `feature/dueltrace-v087-auto-spoils`.

## Demanda e interpretação

O usuário verificou que a projeção de abertura da antiga calculadora de Spoils deve exibir **101 pontos** (dez critérios em zero, 8.000 LP, vitória hipotética por LP) e solicitou **cálculo automático**, sem preencher dez campos durante o duelo.

A fórmula **não teve a base alterada para 101**. Base = 50; vitória por LP = +2; contribuições da tabela X15 para esse estado são +49, resultando em **101**. Alterar a base duplicaria +51 pontos.

## Implementação

- `web/components/desktop/desktop-page.tsx`: a **Calculadora automática de Spoils** substitui o formulário manual; os dez campos e os botões calcular/limpar foram removidos.
- O painel recebe **o mesmo objeto `RankState`** obtido pelo Contador de RANK a cada ~2,2 s, sem uma segunda leitura RAM concorrente. Exibe score, RANK, contadores e contribuições recebidos do motor Python, usando a classificação da ISO selecionada.
- Sem leitura calibrada, chama **uma vez** o motor Python existente `calculate_spoils` com os contadores da abertura e exibe **101 pontos apenas como referência hipotética**, identificada explicitamente como **não proveniente do ePSXe**. O usuário não é induzido a acreditar que os pontos foram lidos em uma ISO sem mapeamento.
- A projeção viva continua condicionada às verificações já existentes no motor: ISO X15 conhecida / binário compatível ou binding RAM por ROM+SLUS+tabela validado em duelos independentes, e **confirmação dos LP exibidos no jogo**. Após a calibração, as alterações do duelo são processadas automaticamente sem inserir ações uma por uma.
- A previsão ao vivo é **se vencer por LP**. O jogo pode terminar por deck-out ou Exodia, situações com bônus diferentes e sem detecção automática confiável no leitor atual.
- Não houve alteração de `RULES`, base, bônus, classes Z/S versus clássicas, RAM, MIPS ou bloqueios de segurança. O catálogo de Drops permanece simplificado conforme v0.8.6.

## Validação prevista

- Teste Python de abertura **101 pontos** e mudanças automáticas de score com `spells` e `remaining_lp` em mock RAM: 101 → 95 → 91 → 89, sem digitar critérios a cada leitura.
- CI Python/Next.js/Windows, SHA-256 e Microsoft Defender; publicação como Preview.
- Na máquina do jogador, usar Remaster X15 no ePSXe, selecionar ISO no DUELTRACE, confirmar LP reais na leitura inicial e verificar em duelo que pontos e RANK respondem às ações. Confirmar se o jogo efetivamente está executando a mesma ISO selecionada, pois o aplicativo não consegue certificá-la sozinho.
- Em mods sem mapeamento válido, painel mostra apenas referência de 101, nunca um score supostamente lido ao vivo.
- Divergências históricas (46 calculado / 45 observado e 50 S-TEC) continuam em investigação; não alterar a fórmula/bandas sem confirmação do jogo.

## Próximo prompt

> CONTINUAR DUELTRACE v0.8.7. Repo https://github.com/guibatoni/appassist, branch `feature/dueltrace-v087-auto-spoils`. A v0.8.7 transformou a calculadora manual numa visualização automática vinculada ao mesmo get_rank que a Central de Duelo já consulta a cada ~2,2 s. O algoritmo de Spoils continua base 50, LP +2, dez categorias, com pontuação de abertura 101 no cenário padrão; a simulação inicial de 101 é marcada como **não lida do jogo**. Quando RAM e LP são validados, score, breakdown e RANK passam a acompanhar os contadores automaticamente. Não habilite mods sem binding confirmado, não invente reconhecimento da ISO carregada. Validar com ePSXe real e corrigir divergências de 1 ponto e 50 S-TEC documentadas, preservando catálogo Drops, fusões, scanner, atualizador sem assinatura obrigatória (origem/hash) e arquivos locais. Conferir commit, PR, CI e testes antes de declarar a entrega final.
