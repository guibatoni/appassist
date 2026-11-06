# DUELTRACE — Backup Etapa 28 (06/11/2026)

## Continuidade obrigatória

- Código: `guibatoni/appassist` (**privado**). Branch Etapa 28: `feature/dueltrace-v097-forensic-consistency-v28`, derivada de `feature/dueltrace-v097-private-evidence-sync-v27` (PR #75).
- Etapa 27 trouxe sincronização segura com o repositório GitHub privado `guibatoni/dueltrace-evidencias`. A comunicação foi comprovada por arquivo em `reports/61d58d835246/79dd2bf007694191.json`. Não publicar relatórios no repositório de código por padrão.
- Existe automação no ChatGPT para comparar relatórios a cada hora e notificar resultados relevantes, **não** leitura direta contínua da RAM.
- Preservar Biblioteca de **722 cartas**, artes, leitura de 5 cartas da mão, layout atual e gates de RANK/drops. Sem merge na `main`.

## Última evidência remota observada

Em 06/11/2026 às 22:37:35 UTC, o JSON remoto ainda estava ativo (`running=true`) e registrava **127 amostras, 39 mudanças, 39 mãos e 39 sondas de adversário legíveis, byte candidato 5, quatro pares de campos legados de LP**, sem RANK pronto. A âncora da mão funcionou. **Nem byte 5 nem campos legados de LP têm identidade/semântica comprovada no GOG.**

## Entrega de código da Etapa 28

- `scanner/dueltrace_live_forensics.py`: triagem local agregada dos eventos sanitizados.
- `scanner/dueltrace_web_bridge.py`: `forensicReview` na resposta de status, sem mudança no JSON remoto.
- `web/lib/desktop.ts`, `web/components/desktop/desktop-page.tsx`: avisos específicos de evidência provisória.
- `tests/test_dueltrace_live_forensics.py`: testes offline sintéticos para constância, variação, invalidez e não promoção.
- `docs/DUELTRACE_PHASE28_FORENSIC_CONSISTENCY.md`: protocolo científico e bloqueios atuais.
- A versão Etapa28 **não valida IDs, LP, duelos, drops, RANK ou fusões**. CI/Windows e, posteriormente, validação no ePSXe continuam pendentes até verificação explícita.

## Prioridade depois da Etapa 28

1. Localizar origem MIPS do ID de adversário do GOG (não presumir endereço do retail). Estabelecer fonte independente para associar um ID em RAM a um nome real.
2. Instrumentar, após prova do executável, começo/fim de duelo e recompensa efetivamente entregue; cruzar ID→bloco físico→grupo RANK das 160 matrizes apenas com evidência.
3. Encontrar e executar/validar a rotina MIPS de fusões; observar inputs e output sem deduzir receita de mudança de mão.
4. Auditar cada alteração, manter hipóteses separadas de confirmações e atualizar documentação/backup a cada etapa.

## Limitações operacionais e segurança

O ChatGPT pode consultar o repositório privado via GitHub conectado e analisar cada nova versão, mas não fica executando esta conversa 24h nem tem acesso ao processo Windows. A automação faz verificações por hora, enquanto o DUELTRACE envia somente relatórios autorizados e saneados. Manter `main` intacta e nenhum dump/ROM/chave no repositório.
