# DUELTRACE v0.21.0 — suporte de RANK ao Remaster X15 PT-BR

Data: 14/11/2026  
Repositório: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v0.21.0-remaster121-rank-labels`  
Base: `feature/dueltrace-v0.20.1-overlay-calculator-parity` (PR #124)  
Plataforma: Windows / ePSXe.

## Mod analisado

Arquivo local fornecido: `Remaster_121_X15_Descricoes_PTBR_COMPLETO(1).bin`  
SHA-256 da imagem: `b60b8dd798aca75bf685947ffbdede932af87c95d00129dd8fdda1046f05c0a1`  
Tamanho: 114.751.728 bytes, imagem raw Mode 2 em setores de 2.352 bytes.  
Executável: `SLUS_014.11`; arquivo de dados: `DATA/WA_MRG.MRG`.

## Evidência e limites

- A tabela de pontuação no `WA_MRG.MRG` tem SHA-256 `dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0`, igual à tabela X15 já conhecida.
- Ela aparece 40 vezes consecutivas no offset e espaçamento esperados.
- O `SLUS_014.11` tem SHA-256 `3944b30d6d19b762eaec7ac7f9864f064c1595659bc9655655212b7402c59062`, diferente do executável X15 previamente validado.
- A edição mostra `Z-POW`, `S-POW` e `S-TEC` nos ranks e filtros somente para o SHA exato desta imagem. O cálculo de RANK ao vivo e a execução da fórmula não são declarados validados; permanecem indisponíveis para este executável até teste específico.
- O repositório recebe somente fingerprints e código, nunca o BIN, SLUS ou WA.

## Alterações preparadas

- `scanner/scanner_multiiso.py`: identifica esta imagem por SHA e descreve a compatibilidade da tabela sem chamar o executável de validado.
- `scanner/dueltrace_rank_system.py`: separa a ISO de nomenclatura reconhecida do SHA que autoriza o modelo ao vivo; mapeia os três ranks e filtros para a variante.
- `scanner/dueltrace_drops.py`: considera a nomenclatura X15 na seleção das opções de rank.
- `scanner/importador_perfis.py`: marca os nomes como verificados apenas quando a tabela detectada tem hash, contagem, offset e espaçamento esperados. Regras pontuadas continuam não extraídas.
- `scanner/dueltrace_update_checker.py`: versão corrente 0.21.0.

## Patch notes

### Novidades
- Reconhece a edição Remaster X15 com descrições PT-BR pelo SHA da ISO.
- Exibe Z-POW, S-POW e S-TEC nos ranks e filtros do mod.

### Melhorias
- Mantém o cálculo ao vivo bloqueado quando o executável não corresponde ao X15 validado.

### Correções
- Evita exibir os dez ranks clássicos para esta ISO identificada.

## Validação pendente

O CI do Windows será acompanhado no PR. Antes de declarar o rank ao vivo validado, é necessário iniciar o mod no ePSXe, comparar ranks de duelos reais e investigar as rotinas do executável desta variante.
