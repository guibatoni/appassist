# DUELTRACE v0.9.7 Preview — entrega de integridade por ISO

## Objetivo e base

Evoluir o código existente a partir de `aef5a34a595d63d36d89f947ee8c0ec132ca69be`
(v0.9.6), com prioridade nos limites dos nomes GOG e na associação segura dos
catálogos. Branch: `feature/dueltrace-v097-opponent-validation`.
Este relatório descreve código e testes locais; não anuncia um pacote Windows
publicado nem compatibilidade confirmada do GOG MOD.

## Implementações

- Decoder compartilhado por glifos, leitura delimitada e evidência de todos os 39 ponteiros, sem remover `v` nem aceitar terminadores alternativos por hipótese. A interface secundária mostra byte/glifo final, terminação, limites e inconsistências dos ponteiros.
- Validação estrutural das 722 cartas, 39 oponentes e das 117 matrizes efetivamente reconstruídas. IDs, atributos, pesos e proveniência por SHA são conferidos. A API recusa catálogos incompletos; candidatos permanecem em quarentena, com CSVs preservados.
- Adaptador WA explícito e limites de leitura. Cabeçalho PS-X EXE, payload, endereços e entrada são conferidos antes de usar candidatos. A leitura dos campos do cabeçalho no analisador MIPS também foi corrigida.
- RANK somente lê RAM para SHA X15 exato ou binding próprio validado; igualdade de executável/tabela é pista estática. Fórmula de Spoils preservada: projeção histórica 101, 76→B-POW e 29→B-TEC; classes X15 continuam exclusivas de seu SHA.
- Cache geral versionado mesmo sem artes, compartilhado com o monitor de pastas. Uma revisão antiga é reanalisada uma vez; a mesma mídia/revisão reutiliza o perfil sem novo hash, preservando receitas elegíveis da mesma ISO.
- Atualizador e publicador reconhecem branches explícitas como `v0.10.0` e o formato legado `v096`. Comparação numérica, origem oficial e rejeição de versões ambíguas preservadas.
- Geist e Exo 2 locais com origem, hashes e licenças OFL, evitando download de fontes durante o build. README e plano mestre atualizados; filtros CI abrangem todos os módulos e testes novos.

## Validação nesta instância Linux

| Verificação | Resultado |
| --- | --- |
| `python -m compileall -q scanner tests tools` | Aprovado |
| `python -m unittest discover -s tests -v` | 472 testes: 468 aprovados, 4 ignorados por exigirem Windows |
| `npm ci` em `web/` | Aprovado, lockfile preservado |
| `npm run build` em `web/` | Aprovado, TypeScript e export estático |
| `python tools/security/verify_web_css.py` | Aprovado; CSS compilado e servido localmente |
| Smoke Chromium do export | Diagnóstico preserva `ABCv`/glifo `0x04`, mostra auditoria e quarentena; quatro rotas, sem erros JavaScript nem pedidos externos, com API nativa **sintética** |
| Parser Bash de publicação | Sintaxe e 38 casos comparados ao parser Python, sem executar publicação |
| `npm audit --omit=dev --audit-level=moderate` | Nenhuma vulnerabilidade de produção |
| `npm audit --audit-level=high` | Limite aprovado; oito pacotes dev com um advisory moderado pendente |
| `git diff --check` | Aprovado |

A base v0.9.6 passou 419 testes com quatro ignorados nesta máquina antes das
mudanças. O smoke Chromium verifica renderização e navegação; não comprova a
janela WebView2, o seletor Windows ou a leitura de um emulador real.

## CI e distribuição observadas após o push

- Commit do código publicado: `f4a90a192bd78422d930deca15ea22fc62e5e093`.
- [Workflow Windows #41908557284](https://github.com/guibatoni/appassist/actions/runs/41908557284): **Success**, duração total observada de 3m27s. O job de build e o job de publicação concluíram.
- [Preview oficial v0.9.7](https://github.com/guibatoni/appassist/releases/tag/preview-v0.9.7-r41908557284): página publicada e conferida, vinculada ao commit do código acima. O pacote é uma Preview Windows sem assinatura digital, conforme seus avisos; não equivale a uma release estável ou a validação real do GOG.
- Artefato do workflow: `DUELTRACE-Windows-Preview-Unsigned-Security-Scanned`, 43,3 MB. Digest do artefato observado: `sha256:5c45123c4e43ea8212aa9b8f54cb3a81527bf2b11111d2932155a4c453bef5a4`. Esse digest identifica o artefato do Actions, não deve ser confundido com o hash do ZIP interno da release.
- A consulta foi possível pela página pública do GitHub, apesar do bloqueio da API. O PR automático permanece pendente; nenhum merge em `main` foi realizado.
- `install_script` e `start_skill` do ambiente foram atualizados no rascunho para incluir o fluxo WebUI e exercitados na instância atual. Essa configuração ainda requer revisão/salvamento/publicação pelo usuário; scripts salvos não comprovam restauração em outra tarefa.

## Limitações e próxima validação

1. A ISO, `GOG_VNT.223` e `GOSD/GOG_SD1.23` reais não estão disponíveis. A recuperação dos 39 nomes, a identidade/atributos das 722 cartas e a associação real dos 4.543 drops históricos continuam pendentes. As contagens dos testes são sintéticas, não resultados do GOG.
2. Tabelas de nomes com reutilização de sufixos entre ponteiros ficam ambíguas até existir adaptador comprovado. Aliases exatos continuam suportados.
3. Guardas novas cobrem RANK; a leitura da mão mantém o mecanismo anterior e ainda exige validação por mod. Fim de duelo e tipos de vitória não foram comprovados em RAM real nesta entrega.
4. Empacotamento Windows, WebView2, Defender, instalador/atualização/reinício e duelos reais precisam do workflow e de uma máquina Windows. Nenhum desses resultados é inferido do build Linux.
5. A pendência moderada de desenvolvimento está detalhada em [auditoria de dependências](DUELTRACE_V097_DEPENDENCY_AUDIT.md). Não há patch compatível publicado para o caminho instalado; não se aplicou downgrade, override fora do contrato ou supressão.
6. A API `api.github.com` recebeu negativa da política de rede. O domínio foi adicionado ao rascunho do ambiente; salvar/publicar essa configuração é ação do usuário. A branch foi enviada e a CI/release foram conferidas pelas páginas públicas, mas a criação automática do PR ainda precisa de acesso à API.

Próximo passo determinante: gerar `relatorio.json` da revisão 7 com a ISO GOG
local, conferir os 39 registros/glifos/limites com o jogo e só então implementar
um adaptador de terminação comprovado. Depois validar IDs/atributos das cartas
e os pools de drops em duelos. Seguir os critérios do
[plano mestre](DUELTRACE_MASTER_PLAN.md), preservando isolamento por SHA.

## Arquivos modificados

- `.github/workflows/validar-webui-desktop.yml`
- `README.md`
- `docs/DUELTRACE_CATALOG_INTEGRITY.md`
- `docs/DUELTRACE_MASTER_PLAN.md`
- `docs/DUELTRACE_V097_DELIVERY.md`
- `docs/DUELTRACE_V097_DEPENDENCY_AUDIT.md`
- `docs/DUELTRACE_V097_GOG_NAME_EVIDENCE.md`
- `docs/DUELTRACE_V097_LAYOUT_ADAPTERS.md`
- `docs/DUELTRACE_V097_RANK_RAM_GUARDS.md`
- `docs/DUELTRACE_V097_SCAN_CACHE.md`
- `scanner/auto_mods.py`
- `scanner/dueltrace_catalog_validation.py`
- `scanner/dueltrace_drops.py`
- `scanner/dueltrace_layout_discovery.py`
- `scanner/dueltrace_mod_diagnostic.py`
- `scanner/dueltrace_name_boundaries.py`
- `scanner/dueltrace_preview_updates.py`
- `scanner/dueltrace_rank_diagnostic.py`
- `scanner/dueltrace_rank_profile_live.py`
- `scanner/dueltrace_update_checker.py`
- `scanner/dueltrace_web_bridge.py`
- `scanner/fm_rank_mips_evidence.py`
- `scanner/importador_perfis.py`
- `scanner/scanner_multiiso.py`
- `tests/test_dueltrace_art_cache.py`
- `tests/test_dueltrace_catalog_validation.py`
- `tests/test_dueltrace_drops.py`
- `tests/test_dueltrace_layout_discovery.py`
- `tests/test_dueltrace_legacy_rank_transfer.py`
- `tests/test_dueltrace_mod_diagnostic.py`
- `tests/test_dueltrace_name_boundaries.py`
- `tests/test_dueltrace_name_decoding.py`
- `tests/test_dueltrace_partial_iso_evidence.py`
- `tests/test_dueltrace_preview_installer.py`
- `tests/test_dueltrace_preview_updates.py`
- `tests/test_dueltrace_rank_capture.py`
- `tests/test_dueltrace_rank_diagnostic.py`
- `tests/test_dueltrace_rank_profile_live.py`
- `tests/test_dueltrace_scan_cache.py`
- `tests/test_dueltrace_web_bridge.py`
- `tests/test_fm_rank_mips_evidence.py`
- `web/app/fonts/Exo2-OFL.txt`
- `web/app/fonts/Exo2-Variable.ttf`
- `web/app/fonts/Geist-OFL.txt`
- `web/app/fonts/Geist-Variable.ttf`
- `web/app/fonts/README.md`
- `web/app/layout.tsx`
- `web/components/desktop/desktop-page.tsx`
- `web/lib/desktop.ts`
- `web/public/licenses/fonts/Exo2-OFL.txt`
- `web/public/licenses/fonts/Geist-OFL.txt`
