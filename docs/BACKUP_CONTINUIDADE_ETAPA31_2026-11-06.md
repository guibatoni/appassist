# DUELTRACE — Backup de continuidade, Etapa 31 — 06/11/2026

## Código e estado
- Repositório privado `guibatoni/appassist`, branch `feature/dueltrace-v097-iso-forensic-lab-v31`, base commit Etapa30 `481e621dfa6e4d4e7376b243615db6baf4b8e342` (PR #78 aprovado no CI, ainda draft e não integrado à main).
- Etapa31 acrescentou o **Laboratório Forense de ISOs** com leitura local somente de ISO/BIN cadastradas e salvas. **Não mesclar na main** sem autorização. Não modificar leitura de mão, 722 cartas, artes, perfis verificados, RANK/drop/fusões habilitados nem sincronização RAM existente.
- Documento técnico: `docs/DUELTRACE_PHASE31_ISO_FORENSIC_LAB.md`.
- A Etapa31 ainda depende de verificação CI Windows da HEAD e execução no PC. Não afirmar que foi instalada ou que analisou as ISOs no Windows.

## Imagens de teste disponíveis na conversa original
- `RISING OF WICKED GODS 1.3.5 ver 2 - Drop 15 (NDC).bin` SHA `06b3a87fe7c29b0565b053718f9308212efbc9f7b9c20b1b7f7bcfc425f71b63`.
- `ENHANCE EDITION FINAL4 (Drop x15)(NDC).iso` SHA `6a1a897db35c5cf69ed631deba9793882ab2d6e9d71cf57d577267786bc10150`.
- Controle positivo `FM Galaxy Of Gods NT Mod 2025 - Drop 15 (SEM REQUISITOS).iso` SHA `8954b9d603270200bcf5c3edf404d5d18c772c4fb058bc017916f7c73c059d15`.
- Nenhum byte bruto/ISO/arte foi commitado em GitHub. Evidência estrutural Etapa30 preservada na Biblioteca `/DUELTRACE - Desenvolvimento/PROJETO_ATUAL/`.

## Descobertas anteriores, para regressão
- Rising: 722 cartas e artes; 39 adversários com `FD+u16+FF` e campo uniforme; 39 blocos de drops desde `0x2421800` em WA, 117 tabelas mascaradas; sete bancos de fusão, 5555 receitas, 3 pares contraditórios (6 detecções).
- Enhance: 722 cartas e artes; 39 nomes FD, 38 campos uniformes e um +1; 40 blocos consecutivos desde `0xE99800`, 2 janelas candidatas de 39; 117 tabelas no offset padrão, 7 bancos e 24953 receitas sem conflito.
- Galaxy positivo: 722 cartas e artes, 39 nomes convencionais, 39 blocos de drops, sete bancos, 18553 fusões sem conflitos.
- A identidade real ID→adversário, a seleção de bloco/grupo RANK em runtime e fusões contraditórias continuam sem prova; não promover por contagem ou semelhança.

## Implementação Etapa31
- `scanner/dueltrace_iso_forensic_lab.py`: inspeção integral/reprodutível do arquivo cadastrado (hash SHA antes, arquivo/mtime após), indexação ISO9660, seleção segura de EXE/WA, contagens de cartas/oponentes, candidato estático MIPS, família 39x4 e janelas, 117 drops, 7 bancos de fusão e 722 artes/miniaturas. Relatório somente de metadados e contagens.
- `scanner/dueltrace_web_bridge.py`: `audit_mod_iso` registra relatório em `home/iso_forensics/<sha>.json`, `upload_iso_forensic` só para arquivo que ainda corresponde a SHA cadastrado.
- `scanner/dueltrace_web_security.py`: protege ambos por token pywebview.
- `scanner/dueltrace_private_evidence_sync.py`: transmissão **apenas por clique/confirmacão** de JSON forense com schema fechado para repositório privado pré-autorizado; endpoint `reports/iso-forensics/<sha12>.json`. O relatório RAM continua com esquema/privacidade independentes. Nunca envia ISO, imagens, caminhos, cartas/fusões completas, RAM, tokens.
- `web/lib/desktop.ts` e `web/components/desktop/desktop-page.tsx`: controles **Auditar ISO**, **Copiar relatório forense** e **Enviar relatório privado**, com alertas de janela ambígua e receitas conflitantes.
- Testes novos `tests/test_dueltrace_iso_forensic_lab.py` e regressões de autorização/tentativa de envio/modificação do arquivo em `tests/test_dueltrace_web_bridge.py`, `tests/test_dueltrace_private_evidence_sync.py`.

## Protocolo de próximos testes, com a versão Windows Etapa31 após CI
1. Instalar **Preview isolada** sem sobrescrever a instalação funcional do DUELTRACE nem dados da Biblioteca antes de backup.
2. Na Biblioteca de Mods, confirmar/cadastrar as três ISOs, clicar **Auditar ISO** uma por vez. A ferramenta confere SHA antes e salvaguarda os perfis operacionais.
3. Conferir contagens e alertas da UI. Se quiser dispensar copiar JSON manualmente, clicar em **Enviar relatório privado** e confirmar, com sync privada já configurada; verificar `guibatoni/dueltrace-evidencias/reports/iso-forensics/` via conector GitHub do ChatGPT.
4. Cruzar cada relatório com os números reais da Etapa30. Investigar discordâncias no scanner sem apagar dados corretos.
5. Para provar mapeamento do adversário, drops/RANK e fusões em jogo, continuar Live Diagnostics + análise MIPS — ISO estática por si só não basta.

## Restrições
Sem merge/push na main, sem publicação de binários comerciais, sem extrapolar nomes de ranks, sem alteração de licença. Manter PR em draft até CI/Windows real. A automação horária de evidências existe mas não é acesso permanente do ChatGPT à RAM.
