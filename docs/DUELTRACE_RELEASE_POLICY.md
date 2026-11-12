# DUELTRACE — Política obrigatória de versões e avisos

## Prioridade permanente (antes de qualquer novo recurso publicado)

Nenhuma nova Preview do DUELTRACE deve chegar ao usuário sem:

1. **Versão coerente.** O número canônico é `CURRENT_VERSION`, em
   `scanner/dueltrace_update_checker.py`. Uma mudança com novos recursos
   deve avançar a versão SemVer (`0.9.7` → `0.10.0`, por exemplo).
   O nome da branch de release deve declarar a MESMA versão,
   `feature/dueltrace-v<MAJOR>.<MINOR>.<PATCH>-...`.
2. **Patch Notes atuais.** Antes de cada build, atualizar
   `docs/DUELTRACE_UPDATE_NOTES.md`, começando com
   `# DUELTRACE v<versão> — Preview` e incluindo
   `## Novidades`, `## Melhorias` e `## Correções`
   com pelo menos um item legível em cada seção. Não copiar notas de
   versões antigas para sugerir falsamente que são novidades.
3. **Aviso de versão disponível.** O aplicativo consulta o feed oficial
   periodicamente e mostra o estado de nova atualização na interface,
   sem baixar ou instalar executáveis sem clique do usuário.
4. **Aviso após instalar.** A primeira abertura de uma build Preview
   exibe as suas Patch Notes automaticamente, mesmo offline. A leitura
   só é confirmada ao fechar o diálogo; o mesmo build não incomoda
   novamente, mas toda nova identidade de build abre as novas notas.
5. **Notas dentro do executável.** O Windows ZIP contém tanto
   `dueltrace-build.json` (versão, SHA, run) quanto
   `DUELTRACE_UPDATE_NOTES.md`, associados ao MESMO commit.
   A interface jamais apresenta notas de uma release mais nova
   como se fossem novidades da versão já instalada.
6. **Distribuição verificável.** Antes de publicar, o CI executa testes,
   auditorias, verificação do ZIP e Microsoft Defender; as releases
   Preview exigem identificação do commit e SHA-256. Não desligar
   essas verificações para forçar a publicação.
7. **Preview não é release estável.** O desenvolvimento segue no canal
   Preview até existir validação real do atualizador e executável
   Windows. Não marcar pré-release como estável sem decisão explícita.

## Automação para prevenir esquecimento

O workflow `.github/workflows/validar-webui-desktop.yml` executa
`python tools/security/verify_preview_metadata.py --branch "<branch>"`
antes de compilar. Ele interrompe o pipeline quando versão, branch ou
notas não corresponderem. O manifesto `dueltrace-build.json` recebe
a versão do código, não uma constante copiada no YAML.

Os testes `tests/test_dueltrace_preview_version_policy.py`,
`tests/test_dueltrace_update_notice.py` e
`tests/test_dueltrace_patch_notes.py` protegem este contrato.

## Segurança e privacidade

As notas são lidas de dentro da build instalada, sem rede. O estado
de leitura grava apenas versão e run ID em
`%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\dueltrace_update_notice.json`.
Nenhuma ISO, dado do ePSXe, RAM, carta ou segredo é enviado.

O instalador continua trocando apenas os binários gerenciados na mesma
pasta, usando backup e rollback. Não elimina arquivos do usuário.
