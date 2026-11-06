# DUELTRACE — BACKUP DE CONTINUIDADE ETAPA 27 (SINCRONIZAÇÃO PRIVADA)

**Data:** 06/11/2026. **Estado:** PR draft a ser criado, integração ainda não ativada nem validada em Windows real. **Branch:** `feature/dueltrace-v097-private-evidence-sync-v27`.

## Base canônica e preservação

- Etapa 25: PR #73 `feature/dueltrace-v097-live-diagnostics-v25`, commit testado `089d6773e3d7be92afbd7b6442b814f2d8b611a7`, 754 testes + Windows aprovados, Preview `preview-v0.9.7-r42283346075`.
- Etapa 26: PR #74 `feature/dueltrace-v097-live-probe-evidence-v26`, HEAD base imutável `1bd006c4d497cad59407fa901faae96c3c01acec` (CI concluída com sucesso antes da Etapa27). Dois relatórios reais privados com fingerprint `61d58d835246`, ID candidato `5` persistente, mão e LP mudaram. Nome/ID do executável/bloco/matriz não identificados.
- **Não tocar** na Biblioteca de 722 cartas, artes, leitor de mão, RANK e matrizes existentes. Nenhum ID, fusão, drop, RANK ou nome inventado. Nem merge na main.

## Pedido do usuário

Solicitou conexão remota para coletar diagnósticos automaticamente e facilitar a conclusão de adversários, drops e fusões. A conversa ChatGPT não pode abrir canal direto permanente até a memória do PC nem escutar telemetria na nuvem de maneira invisível. Foi projetada uma **sincronização unidirecional, controlada pelo jogador, para repositório privado GitHub** acessível ao conector do usuário durante a conversa.

## Entrega técnica proposta

- Novo `scanner/dueltrace_private_evidence_sync.py`: transporta somente `LiveDiagnosticsRecorder.export_json()` por HTTPS para o GitHub API, validando novamente forma/tamanho/campos e privacidade do repositório a cada envio. Sem upload se repositório público, não pertence ao destino autenticado ou não contém autorização.
- Credencial GitHub de escopo mínimo salva no Windows DPAPI e nunca na config, logs ou exportação. Não exigir assinatura, servidor pago, arquivo ISO, abertura de porta ou controle remoto.
- Bridge usa thread local sem bloquear coleta, envio a cada ~60s enquanto Live Diagnostics está rodando e nova tentativa final ao parar. Com os dois sistemas desligados, **nenhum tráfego automático**.
- UI em Biblioteca de Mods: configura `usuario/repositorio-privado`, cola fine-grained PAT apenas no app, marca consentimento explícito, verifica e ativa; exibe último envio, erro e botão para desativar/apagar credencial local.
- `web/lib/desktop.ts` e API pywebview protegida: métodos autorizados por token local; nunca expõe PAT em status.
- Testes offline de recusa do público, permissão, limite, sanitação, autenticação e desativação. Aguardar CI e Windows real antes de dizer concluído.
- Documentação: `docs/DUELTRACE_PHASE27_PRIVATE_EVIDENCE_SYNC.md`.

## O que NÃO está pronto

- **Não existe repositório privado de evidências criado/selecionado pelo usuário nem token configurado. Nenhum dado foi transmitido.**
- Nenhuma conexão direta a esta conversa e nenhum acompanhamento automático sem turno do usuário.
- Não foi comprovado ID 5 como adversário nomeado; sem MIPS de IDs→blocos e grupos RANK; fusões pendentes. O envio é apenas transporte dos dados já saneados, não uma rotina de engenharia reversa autônoma.
- CI e Preview da Etapa 27 dependem de confirmação da HEAD.

## Próximos passos

1. Validar toda CI Python/TS/Windows e revisar regressões de segurança.
2. Usuário cria repositório privado **separado do código público**, fine-grained PAT com Contents Read+write só nele, configura diretamente no app Etapa27 e autoriza o GitHub conectado ao ChatGPT a ler esse repositório.
3. Rodar sessão real e confirmar que um arquivo `reports/<fingerprint>/<session>.json` apareceu; desativar token no app e verificar que não é mais possível enviar sem novo consentimento.
4. Aqui na conversa, consultar GitHub privado quando usuário solicitar, analisando evidências e orientando engenharia reversa MIPS e extração de drops/fusões, sempre preservando hipóteses versus fatos.
5. Criar próximo backup na Biblioteca `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/` a cada etapa.

## Política de privacidade

A autorização para **desenvolver** o recurso não habilita nenhuma transmissão. A ativação exige opt-in e credencial criados diretamente pelo usuário no aplicativo. Relatórios antigos/atuais permanecem privados na Biblioteca ChatGPT; não os publicar no repositório público `appassist`.

## Complemento de segurança — envelope remoto

Após auditoria do transporte, foi definido envelope remoto explícito `subject=DUELTRACE Private Evidence Sync` com `transport=github_private_repository`, `syncedAtUTC` e `diagnostics` contendo o JSON original sanitizado. O sinal `diagnostics.networkTransmission=false` refere-se somente ao gravador; o envelope indica upload real. A comparação de adversários, drops e fusões continua não confirmada. A validação CI deve se referir à HEAD atual, não a commits anteriores.
