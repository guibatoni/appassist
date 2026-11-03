# DUELTRACE WebUI 0.7.1 — RANK no Início e Biblioteca de Fusões ilustrada

## 1. RANK na aba Início
Foi acrescentado um painel de RANK com a mesma hierarquia tipográfica das demais seções (título Exo 2, número em destaque, informações em Segoe/Geist).

O DUELTRACE não deve inventar pontuação. A projeção só é possível quando todas as condições são atendidas:
1. O perfil do mod ativo corresponde ao SHA-256 exato do Remaster X15 já analisado no scanner.
2. Existe somente um ePSXe, ou um PID aberto pelo próprio DUELTRACE é conhecido.
3. O bloco de 32 bytes no endereço virtual **candidato** 0xB41990 retorna duas leituras idênticas e plausíveis.
4. O usuário compara os LP atuais no jogo e os confirma explicitamente na UI; devem coincidir com o valor da RAM.

A projeção usa as dez categorias da tabela MIPS extraída daquela ISO, base 50 e resultado hipotético de vitória por LP (+2). O rótulo diz expressamente **projeção se vencer por LP**, não nota final nem rank garantido. O endereço virtual do ePSXe é hipotético; uma coincidência de LP não valida todo o mapeamento, portanto o recurso permanece experimental.

A calibração é mantida somente em memória e descartada após falha de leitura, troca de mod, PID diferente, reinício do contador de turnos ou expiração. Nenhuma RAM ou save é alterado.

Para qualquer outro mod, inclusive FM13 Drop x15, o painel fica visível, mas indica *pontuação não validada nesta ISO*, sem utilizar regras de outro jogo apenas pelo nome.

## 2. Biblioteca de Fusões com texto e imagem
- Cada receita aparece como três miniaturas: **Material A + Material B → Resultado**.
- Nome e ID são exibidos debaixo da imagem, e ATK do resultado e fonte da receita aparecem em rodapé.
- Imagens vêm exclusivamente dos arquivos PNG extraídos e autorizados do mod ativo; quando o scanner ainda não extraiu, aparece um cartão simbólico com nome/ID legíveis.
- Layout responsivo em duas colunas em janelas largas; 12 receitas por página para não carregar centenas de imagens simultaneamente.
- Busca por nome ou ID e paginação preservadas.

## 3. Aceitação e limitações
- Testar cálculos puros, rejeição de leitores inválidos, confirmação de LP, perda de conexão, PID errado, mod desconhecido e acesso protegido por token.
- Compilar a interface Next.js e inspecionar CSS completo via testes automáticos.
- Preservar auditorias npm/pip, Windows Defender, manifesto SHA-256 e o executável legado.
- **Não usar a prévia como versão comercial até validar ePSXe real e obter assinatura digital.**

Referência de engenharia do RANK: investigação anterior da ISO Remaster X15, registrada em `RELATORIO_SPOILS_X15.md` e `Mapa_Memoria_SPOILS_Remaster_X15_Confirmacao_ISO.md` da biblioteca do projeto. Endereços virtuais seguem hipóteses pendentes de validação no Windows do usuário.
