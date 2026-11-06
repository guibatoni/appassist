# DUELTRACE — Backup de continuidade Etapa 29 — 06/11/2026

## Origem e regra central

Repositório privado: `guibatoni/appassist`. Etapa29 branch `feature/dueltrace-v097-iso-differential-v29`, derivada da HEAD da Etapa28 `1e71770f232374b8c9d28e355cf4f223d693237d`. Não fazer merge na `main`. Preserve 722 cartas, artes, leitura das cinco cartas, fusões do perfil positivo, sincronização privada, dados de drops existentes e suas evidências.

## Informação adicional do usuário

Usuário relata **uma ISO personalizada** que o DUELTRACE reconheceu corretamente e que ele conferiu em jogo: cartas, oponentes, fusões e drops funcionam. Isso é uma observação prática positiva e será **referência de regressão**; o nome exato/SHA/arquivo binário desta ISO não apareceu entre os arquivos acessíveis nesta conversa. Não afirmar que a mídia positiva foi inspecionada diretamente.

As ISOs que continuam falhando são GOG MOD 2.2, Rising of Wicked Gods e Enhance Edition. Não atribuir o mesmo layout a todas sem examinar os arquivos reais.

## Resultado da análise do código

O scanner já suporta conteúdo personalizado quando preservado em layouts decodificáveis. Para o GOG há evidência real anterior: `GOG_VNT.223` (PS-X EXE com padding zero físico confirmado), 39 nomes `FD u16 FF`, 39 decks e 117 matrizes no recurso `G0SD/GOG_SD1.23`; janela estrutural de 40 blocos pode admitir deslocamentos distintos de 39. ID de oponente, slot/nome, drops e labels de RANK ainda exigem prova binária/dinâmica. Causas para Rising e Enhance permanecem desconhecidas.

## Código da nova Etapa 29

- `scanner/dueltrace_iso_differential.py`: sumariza relatórios do MultiISO em assinaturas sem conteúdo e compara os estágios cartões, oponentes, recursos, drops e fusões.
- `scanner/scanner_multiiso.py`: adiciona o campo `comparative_family_fingerprint` à saída local. Sem alterar CSV, decoders ou flags de funcionamento.
- `scanner/dueltrace_web_bridge.py`: compara a referência escolhida com até 12 ISOs já cadastradas, lendo somente relatórios locais e metadados de proveniência de receitas, com checagem SHA e diretório autorizado.
- `scanner/dueltrace_web_security.py` e `web/lib/desktop.ts`: acesso autenticado.
- `web/components/desktop/desktop-page.tsx`: botão **Comparar ISOs** na Biblioteca, sem upload automático de ISO ou resultados.
- `tests/test_dueltrace_iso_differential.py` e `tests/test_dueltrace_web_bridge.py`: regressões sintéticas para mods compatíveis, GOG com nomes FD e 40 blocos, privacidade e ausência de promoção indevida.
- Documento: `docs/DUELTRACE_PHASE29_ISO_DIFFERENTIAL.md`.

## Evidência do Live Diagnostics atual

GitHub privado `guibatoni/dueltrace-evidencias`: a sincronização de diagnósticos foi comprovada. Candidato de ID `5` constante em uma sessão com diferentes mãos e campos legados de LP, mas não confirmado como adversário nem como seleção do bloco. RANK ainda sem prova naquele conjunto de eventos.

## Ações seguintes

1. Validar Python/Next.js/build Windows da HEAD Etapa29.
2. Importar na mesma Biblioteca a ISO positiva e as três ISOs com falhas; quando disponível a Preview, selecionar a ISO positiva e clicar `Comparar ISOs`. Isso gera diferenças de estágio localmente.
3. Com relatórios estruturais e, quando autorizado, bytes locais dos executáveis dos mods, implementar adaptadores genéricos para layouts realmente diferentes.
4. Evoluir a sonda MIPS do campo de oponente GOG, critérios de mapeamento de drop e fusões sem quebrar variantes que funcionam.
5. Atualizar documentação e backup após cada etapa; nunca promover hipótese sem prova independente.

## Controle de risco

Nenhuma mídia de jogo, binário de terceiros, dump de RAM, arte, chave ou caminho privado deve ir para o repositório de código. O comparador não precisa do repositório privado de telemetria e não habilita features por semelhança. O app segue funcional com o scanner antigo enquanto a branch nova é validada.

## Complemento 29B — extração de fusões em contêiner renomeado

Além do comparador, foi corrigido o limitador rígido de nome do extrator de fusões. `scanner/extrator_fusoes.py` mantém a interpretação de `WA_MRG.MRG` existente; se estiver ausente, verifica recursos alternativos de forma limitada e só aceita um quando TODOS os 7 bancos são decodificáveis, idênticos e sem conflitos. Se não forem, bloqueia em vez de inventar receitas. Testes sintéticos adicionados em `tests/test_extrator_fusoes.py`. O GOG ainda pode ter bancos em novos offsets e **não foi validado com ISO real nesta etapa**. Confirmar CI final da branch e preservação das extrações da ISO positiva.

## Complemento 29C — automatização no app moderno

`scanner/dueltrace_intelligence.py` agora executa a sonda de sete bancos quando a ISO é importada pela Biblioteca moderna, mas apenas após confirmar o catálogo 722 por SHA, tamanho e data. Reutiliza o extrator 29B que pode reconhecer contêineres renomeados se os sete bancos forem iguais e válidos. Um resultado negativo fica cacheado por versão da ISO para evitar rescans caros; ausência de evidência não bloqueia cartas, artes nem recursos existentes. Testes sintéticos positivos/negativos em `tests/test_dueltrace_intelligence.py`. Sem confirmar receitas em jogo ou ativar drops/RANK.

## Compartilhamento da comparação
A Biblioteca oferece **Copiar resumo estrutural**, disparado pelo usuário, com metadados sanitizados e sem ISO/ROM/arte/receitas. A autorização da Etapa27 não foi ampliada silenciosamente para envio de relatórios estáticos. Para investigar GOG, Rising e Enhance, o usuário poderá selecionar a ISO positiva e colar a comparação aqui.
