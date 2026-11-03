# DUELTRACE v0.7.4 — Registro de continuidade

Repositório: https://github.com/guibatoni/appassist
Branch: feature/dueltrace-v074-drops-ranks-frames
Pull Request: https://github.com/guibatoni/appassist/pull/24
Base segura: security/dueltrace-trusted-distribution-v073 (PR #23, 7a327f6350)

## Implementado
1. Barra superior sem Motor Python conectado; mostra apenas ISO ativa.
2. Tela de fusões sem Extraída da ISO x7; procedência preservada no backend.
3. Planejador de cadeias de 2 a 5 cartas, com duas cartas no conjunto de resultados.
4. Releitura automática de WA_MRG.MRG e SLUS na importação; revisão do parser 4 atualiza o cache.
5. Extração de oponentes e drops com 39 oponentes e 117 tabelas validadas de peso 2048 cada.
6. Nova aba Drops com filtros, busca, probabilidades, molduras originais e ATK/DEF dos monstros.
7. Registros por ID incluem offset do WA, com dados separados por SHA de ISO.
8. Modelos de pontos de RANK conhecidos reconhecidos apenas pelo SHA X15; pontuação em mods desconhecidos pendente de disassembly MIPS.
9. PNGs de cartas e molduras são associados ao ID e tipo vindo do SLUS; teste de paleta por ID.

## Segurança
API de drops exige token pywebview, não abre endpoint público de escrita. Dados não são transmitidos à nuvem.
ZIP Windows continua não assinado: não recomendar que usuários ignorem bloqueios Chrome/Defender/SmartScreen.

## Validação
Consultar GitHub Actions do PR #24 para resultado final de Python/Next.js, auditorias, empacotamento Windows e Defender.
Sem ISO real ou execução do ePSXe nesta sessão: testes são sintéticos, não validam todos os mods.

## Prompt de continuidade
Continue DUELTRACE v0.7.4 no repo https://github.com/guibatoni/appassist, branch feature/dueltrace-v074-drops-ranks-frames, PR #24. Base security/dueltrace-trusted-distribution-v073 PR #23. Preserve toda WebUI moderna, scanner, ePSXe, fusões, rank, biblioteca de cards/mods, proteção de dados e profiles SHA. Nesta etapa removemos Motor Python conectado, removemos Extraída da ISO x7 nas fusões, habilitamos cadeias 2–5, criamos Drops com oponentes, probabilidades e molduras WA por ID e atributos ATK/DEF, forçamos revisão4 do scanner, registramos offsets reais, entregamos modelo de pontos do X15 identificado por SHA e testes sintéticos. Verifique CI do HEAD antes de afirmar aprovado. Falta extração genérica verificável de pontuação rank MIPS para outros mods, testes reais em Windows/ePSXe e assinatura Authenticode antes de distribuição comercial. Ao concluir etapa gere novo prompt com commit, PR, CI, resultados, alterações e pendências.
