# DUELTRACE v0.7.5 — engenharia forense de RANK e atualizador seguro

Data: 03/11/2026.
Repositório: https://github.com/guibatoni/appassist
Branch de trabalho: `feature/dueltrace-v075-rank-forensics-safe-updater`
Branch base: `feature/dueltrace-v074-drops-ranks-frames` (PR #24, commit `181ed51e5c`).

## Resultado técnico

**RANK / WA_MRG.MRG**
- `scanner/fm_rank_tables.py`: extrai diretamente do WA_MRG 40 cópias consecutivas das tabelas de pontos, com blocos de 3 setores de 2048 bytes a partir do setor 7475.
- Cada tabela tem 10 critérios × 5 faixas × 4 bytes = **200 bytes**; cada par contém limite exclusivo u16 little-endian e pontos i16 little-endian.
- Offset relativo `0x16D0` em cada bloco, com offset global inicial `7475*2048+0x16D0`.
- SHA-256 esperado do conteúdo da tabela no Remaster X15 analisado anteriormente: `dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0`. Reconstruímos a tabela sinteticamente a partir do relatório forense real, e seu digest coincide.
- SHA-256 original do SLUS X15 analisado anteriormente: `67ef6a3f7999bc4b0e09f773b07ee1c5da829a4d4686f1f2f6c8d4e2d6425bec`. Identidade completa exige simultaneamente hash da imagem ISO, hash do SLUS e hash da tabela.
- Se as 40 cópias divergem, se falta espaço ou se limiares/pontos são incoerentes, não há pontos apresentados.
- Para mods desconhecidos com as 40 tabelas consistentes, mostra **dez critérios candidatos e cinco faixas extraídas** com nomes genéricos, sem alegar que o SLUS as executa. Base, modificadores por vitória, rótulos e endereços RAM continuam NÃO VERIFICADOS. Inspeção de instruções MIPS de cada mod e teste no ePSXe ainda são necessários.
- O scanner de importação registra automaticamente `rank_analysis`; perfis usam o resultado e a Biblioteca de Drops exibe valores candidatos com alerta.
- Revisão do scanner incrementada para **5** para atualizar dados de perfis antigos.
- CLI opcional local: `python scanner/dueltrace_rank_iso_audit.py "C:\\Jogos\\mod.bin" --report rank.json`, não envia dados do jogo para rede.

**Atualizador**
- `scanner/dueltrace_preview_updates.py`: descoberta dinâmica por execuções **push/success/completed** do workflow do repositório oficial, em vez de lista fixa de branches. Reconhece a futura versão v076 sem precisar conhecer a branch na compilação v075.
- Ordenação por versão semântica seguida pelo ID do build. Recusa versões inferiores, páginas externas, runs de PR e workflows de terceiros.
- UI verifica atualizações automaticamente ao abrir o aplicativo e mostra notificação, mantendo botão manual.
- `scanner/dueltrace_signed_install.py`: infraestrutura de atualização por instalador Windows assinado de uma GitHub Release estável. Requer URL oficial, SHA-256 da API, assinatura Authenticode válida, mesmo editor verificado do executável atualmente instalado e autorização explícita do usuário. Lança instalador assinado para realizar substituição.
- **Gate não liberado**: `TRUSTED_PUBLISHER_SUBJECT=""`. Não há certificado digital nem instalador assinado publicado. O DUELTRACE permanece incapaz de instalar automaticamente builds Preview não assinados. Essa é uma decisão de segurança, não uma falha de implementação.
- Builds Actions não se tornam auto-instaláveis apenas por passarem CI. Produção exige editora validada, assinatura, testes e uma release oficial com instalador.

## Restrições e validação

- O scanner e os testes só produzem/consomem resultados derivados; arquivos do jogo não são incluídos no repositório ou distribuídos.
- Os relatórios forenses históricos X15 confirmam offsets, estruturas e hashes de uma ISO real fornecida anteriormente, mas **nenhuma imagem de jogo original está acessível no ambiente atual** para nova execução do parser sobre o binário. É obrigatório testar as ISOs locais dos mods no Windows.
- Testes Python cobrem duplicações divergentes, faixas inválidas, falsificação de hashes, escolha de versões futuras, atualização insegura e verificação de instalador.
- A interface pode notificar automaticamente de uma nova prévia, mas não instala sem assinatura.
- Não recomendar desabilitar proteção do navegador/Windows; não prometer ausência de malware.
- Executar o GitHub Actions no HEAD deste PR e revisar tipagem, build Next.js, empacotamento Windows, npm/pip audit e Microsoft Defender.

## PROMPT DE CONTINUIDADE

Continue DUELTRACE v0.7.5 para Windows em https://github.com/guibatoni/appassist. Base preservada: `feature/dueltrace-v074-drops-ranks-frames` PR #24 (181ed51e5c). Nova branch: `feature/dueltrace-v075-rank-forensics-safe-updater`, com extrator forense `scanner/fm_rank_tables.py` que lê 40 tabelas WA de 200 bytes (10 critérios×5 faixas), começando no setor 7475 offset 0x16D0, valida SHA da tabela X15 `dffacc...` e comparações estritas do SLUS/ISO. Em mods desconhecidos apresenta somente valores candidatos, sem afirmar execução da rotina MIPS. O scanner importa rank_analysis e a aba Drops exibe proveniência e advertências. O atualizador agora detecta futuras branches por workflow oficial e ordena por versão+build, verifica automaticamente na inicialização e possui infraestrutura para baixar/verificar/abrir instalador de release estável assinado; a instalação automática está propositalmente DESABILITADA até obter identidade de editor e instalador assinados. Os artefatos Actions continuam não assinados; nunca oriente desativar Chrome/Defender. Um CLI local pode gerar evidências das ISOs do usuário, mas **as ISOs reais não estão neste ambiente**: testar localmente no ePSXe e comparar os logs. Verificar o HEAD do PR e Actions antes de dar status concluído. Ao término de cada etapa registrar branch, commit, CI, funcionalidades, pendências e novo prompt de retomada.
