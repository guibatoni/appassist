# DUELTRACE — Etapa 31: Laboratório Forense de ISOs

Data: 06/11/2026. Base: Etapa30 PR #78 `feature/dueltrace-v097-real-iso-evidence-v30`. **Branch isolada, sem merge na main.**

## Objetivo

Instrumentar o aplicativo Windows para reproduzir a investigação de cartas, adversários, RANK, drops, fusões e artes **diretamente em cada ISO/BIN cadastrado**, preservando a ISO funcional de referência (Galaxy of Gods) e evidências específicas de Rising e Enhance. O leitor nunca altera a imagem, os perfis da Biblioteca nem flags de compatibilidade.

## Fluxo para o jogador

Na **Biblioteca de Mods**, expandir a ISO e clicar **Auditar ISO**. O DUELTRACE fará uma auditoria local do arquivo de origem cadastrado e:
- confere SHA-256 **integral** e detecta alteração de tamanho, data/identidade do arquivo durante a inspeção;
- identifica geometria PS1, número de arquivos ISO9660 e executáveis PS-X EXE com eventual preenchimento físico zero verificado;
- redecodifica 722 nomes/atributos de cartas do executável e busca 39 adversários por sondas alternativas, incluindo a variante `FD u16 FF` com uma exceção de metadado `+1`;
- varre o recurso WA por famílias 39×4, distinguindo 39 blocos únicos e **40 blocos com duas janelas possíveis**; revalida as 117 matrizes em formato tradicional ou realocado;
- reanalisa **todos os 7 bancos de fusões**, conta receitas e pares conflitantes sem atribuir resultado certo a receitas ambíguas;
- revalida **722 artes grandes e 722 miniaturas**, registrando apenas contagem/quantidade de cópias divergentes;
- coleta **número de candidatos estáticos MIPS para RANK** sem declarar rotina executada/validada;
- armazena **somente um relatório numérico sanitizado** em `<catalog.home>/iso_forensics/<sha256>.json`, separado do perfil operacional, e permite **Copiar relatório forense**.

Uma fonte modificada ou com SHA diferente do cadastro deve ser reimportada/reanalisada. Diagnósticos parciais ficam separados por subsistema; nunca criam correspondência adversário→drop nem alteram RANK. Se o contêiner WA tiver nome modificado, o seletor de recurso exige **sete bancos de fusões idênticos e sem conflitos** para escolhê-lo por conteúdo.

## Transferência para o GitHub privado, somente com ação explícita

Novo botão **Enviar relatório privado**, disponível depois de Auditar ISO. O usuário confirma a ação individualmente, sem compartilhar token no chat. É necessário já ter ativado a sincronização privada com repositório GitHub verificado e protegido pelo Windows DPAPI.

- O serviço reabre a ISO cadastrada e **recalcula SHA-256** antes de qualquer transferência de relatório salvo.
- Validador de esquema fechado no módulo `scanner/dueltrace_private_evidence_sync.py`: recusa campos extras, strings com caminhos, dados arbitrários, bytes, tokens, payloads grandes e qualquer indicação de ativação de dados no jogo.
- Só conecta por HTTPS a `api.github.com`, verifica que o destino é privado e grava em `reports/iso-forensics/<fingerprint12>.json`. O envelope identifica `transport=github_private_repository_explicit_user_action` e a data. Como é um resumo por SHA, auditorias posteriores atualizam o arquivo, com histórico de commits no próprio GitHub.
- O fluxo **não** amplia o envio periódico do Live Diagnostics e **não** envia a ISO, cartões individuais, receitas de fusões, artes, diretórios do PC, RAM bruta, nomes de adversários, segredos ou bytes do executável.
- O ChatGPT conectado ao GitHub poderá consultar os relatórios quando o usuário solicitar, e a automação horária existente poderá investigar a pasta de evidências quando configurada para ela. Não existe conexão direta do ChatGPT ao ePSXe nem processamento contínuo desta conversa.

## Arquivos novos/alterados

- `scanner/dueltrace_iso_forensic_lab.py`: laboratório de leitura diretamente da mídia original e summary sanitizado.
- `scanner/dueltrace_web_bridge.py`: métodos `audit_mod_iso` e `upload_iso_forensic`, com source/sha check, relatório local e confirmação de entrega.
- `scanner/dueltrace_web_security.py`: ambos protegidos pela capability local pywebview.
- `scanner/dueltrace_private_evidence_sync.py`: validador estrito e upload **opt-in** isolado do canal de Live Diagnostics.
- `web/lib/desktop.ts`, `web/components/desktop/desktop-page.tsx`: UI com contagens, alertas de ambiguidades/conflitos e botões de cópia/envio explícito.
- Testes: `test_dueltrace_iso_forensic_lab.py`, `test_dueltrace_private_evidence_sync.py`, `test_dueltrace_web_bridge.py`, todos com mocks de fonte e sem binários comerciais no repositório.

## Cenários obrigatórios de validação

| ISO | Expectativa estrutural da auditoria (Etapa30) | O que continua pendente |
|---|---|---|
| Galaxy of Gods NT 2025 | 722 cartas, 39 nomes convencionais, 7 bancos idênticos, 18.553 fusões, 722 artes, 117 grupos | Provar ID, grupo RANK por MIPS se aplicável |
| Rising of Wicked Gods 1.3.5 | 722 cartas, 39 nomes `FD u16 FF`, WA em `0x2421800`, 117 grupos realocados, 7 bancos, 5.555 receitas e **3 pares não ordenados conflitantes**, 722 artes | Resolver conflitos e provar ID/RA​​NK/drop em duelo |
| Enhance Edition Final4 | 722 cartas, 39 nomes `FD u16 FF` com uma exceção `+1`, **40 blocos e duas janelas de 39**, 24.953 fusões, 722 artes | Determinar janela correta pela execução |
| GOG MOD 2.2 | Scanner anterior leu 722 cartas; sondas de adversários/drops ainda provisórias | Prova independente dos offsets MIPS e RANK |

Esses números são **expectativas de regressão** extraídas da análise real anterior. O botão `Auditar ISO` foi implementado agora, mas ainda deve ser testado com estas ISOs no Windows; não afirmar que o novo build reproduziu os números até realizar os testes.

## Segurança e regressão

A suíte deve reprovar adulterações, bytes/arquivos enviados inadvertidamente, token não autorizado, ISO modificada durante leitura, ou falsos estados de RANK. O relatório não contém linhas de fusões individuais nem probabilidade calculada por nome de adversário.

**Não publicar o app nem fazer merge** sem CI Windows da HEAD e um teste manual no computador do usuário. Para retorno dos resultados, solicitar as auditorias privadas de cada ISO e continuar a engenharia reversa com os dados reais.
