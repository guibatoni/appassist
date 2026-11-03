# DUELTRACE WebUI v0.7.3 — Etapa 2: integridade gráfica e dados das cartas

Atualizado em 2026-11-03. Este registro evita perda de contexto entre conversas.

## Bases e versões
- Repositório: https://github.com/guibatoni/appassist
- Última prévia Windows fornecida: DUELTRACE-WebUI-v0.7.2-Windows-Preview
- Base de código v0.7.3: `feature/dueltrace-v073-iso-deep-assets-and-card-text` no commit `659af12eb286e29b95eb4863020ef633d1717789`
- Branch de trabalho: `feature/dueltrace-v073-assets-hardening`
- PR rascunho: https://github.com/guibatoni/appassist/pull/21
- Não realizar merge na main sem validação integral.

## O que está implementado
1. `scanner/fm_deep_assets.py`: extração original WA_MRG de artes grandes 102x96, miniaturas 40x32, seis quadros de duelo 52x60 em 8bpp com CLUT de 256 cores; prévias por ID e tipo. Corrigido status de extração completa para não punir cópias de miniatura divergentes; as divergências continuam no relatório. SHA da ROM deve ter 64 caracteres hexadecimais.
2. `scanner/fm_card_text.py`: descrições decodificadas com ponteiros e IDs do SLUS. Texto de efeito não constitui mecânica comprovada.
3. `scanner/scanner_multiiso.py`: leitura completa do WA quando a extração de arte está ativa; SLUS é lido; ISO original é somente leitura. `scanner/importador_perfis.py`: perfil local com dados extraídos.
4. `web/components/desktop/desktop-page.tsx`: ATK e DEF de monstros exibidos por componente reutilizável em mão, detalhe, grade de biblioteca e fusões. Níveis e IDs das duas Estrelas Guardiãs aparecem no detalhe quando disponíveis. Cartas não monstruosas não recebem estatísticas fictícias.
5. `scanner/dueltrace_web_bridge.py` e `web/lib/desktop.ts`: distinguem `frameStyles` (molduras WA únicas) de `framedCards` (prévias por carta), incluindo resumo de reanálise.
6. Biblioteca de Mods distingue explicitamente textos indicativos de efeito, molduras WA e cartas emolduradas.
7. Testes de regressão adicionados a `tests/test_fm_deep_assets.py` e `tests/test_dueltrace_web_bridge.py`.

## Execução de CI
- Primeira tentativa: falhou por escapes `\\n` literais dentro de código Python (corrigido).
- Execução no commit `98eb6f23` concluiu com sucesso: https://github.com/guibatoni/appassist/actions/runs/41696049254
- Commits posteriores da WebUI/bridge/testes precisam passar pelo CI antes de integrar. Consulte o Actions no PR #21 para a última execução; não afirmar sucesso sem verificar.
- Vercel pode reportar limite de implantação, separado do CI Windows.
- Não há executável v0.7.3 validado e distribuído nesta etapa.

## Limitações honestas
- A execução de efeitos durante o duelo não foi comprovada apenas por texto do jogo.
- A conformidade de molduras/cores em todos os mods exige inspeção real em Windows/ISO de cada versão.
- A WebUI em navegador fora do aplicativo não acessa arquivos locais nem o ePSXe.
- Não distribuir ROM, executável SLUS, WA_MRG, cartas ou imagens extraídas com o aplicativo.

## Prompt de continuidade
Continue o projeto **DUELTRACE WebUI para Windows** do repositório https://github.com/guibatoni/appassist, mantendo todo o trabalho da v0.7.3, integração com ePSXe, bridge Python, bibliotecas de cartas/mods/fusões, leitura por SHA e segurança local. A última prévia baixada é a v0.7.2 Windows Preview, mas a base de código é a branch `feature/dueltrace-v073-iso-deep-assets-and-card-text` commit `659af12`. A branch atual de trabalho é `feature/dueltrace-v073-assets-hardening`, no PR #21. Já foram corrigidas divergências de miniaturas e validação SHA, padronizado ATK/DEF para monstros nas telas, incluídos IDs das Estrelas Guardiãs no detalhe, e separados contadores de molduras WA e cartas emolduradas. Consulte o GitHub Actions do commit atual: o commit `98eb6f23` passou, mas commits mais recentes podem estar pendentes. Próximos passos: conferir CI do PR #21, corrigir eventuais testes/compilação, validar numa ISO real a arte 8bpp e CLUT, melhorar descrições/efeitos respeitando origem e confiança, fazer testes Windows e somente então gerar uma nova prévia. Não apagar funções, não importar dados fictícios dos componentes de demonstração, não declarar efeitos comprovados sem teste. No fim de cada etapa, criar e guardar um novo prompt de continuidade com URL, branch, último commit, CI, o que foi feito e pendências.
