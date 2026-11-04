# DUELTRACE v0.8.5 — Atualização de Preview a partir do GitHub Releases

**Base:** v0.8.4 (PR #34, commit `923f99955a166f9306520016d5c023aebad15ac0`).  
**Branch:** `feature/dueltrace-v085-preview-auto-update`.

## Objetivo

Instalar novas prévias diretamente pelo botão **Atualizar automaticamente pelo GitHub**, sem exigir certificado de assinatura digital durante o desenvolvimento. Não desabilitar Defender, SmartScreen, antivírus ou verificações de origem/integridade.

## Publicação

A CI Windows valida testes, npm/pip audit, compila Next.js, verifica conteúdo do pacote, valida ZIP, executa Microsoft Defender e envia Artifact. Um segundo job (somente push em branch de versão oficial) publica o mesmo ZIP em **GitHub Releases** como pré-release pública, tag `preview-v<versão>-r<run_id>`. Metadados do release contêm target SHA do commit, tag com versão e run, e asset com SHA-256 calculado pelo GitHub.

Isso evita baixar diretamente de GitHub Actions Artifacts com credenciais do usuário. Releases estáveis continuam separados e exigem assinatura Authenticode.

## Atualizador Desktop

- Busca pré-releases oficiais públicas, com comparaçao semver e run_id.
- Recusa downgrade, tags inesperadas, host alternativo, URLs de arquivos alteradas, SHA-256 ausente, tamanho inválido.
- Solicita confirmação explícita para a Preview **não assinada**.
- Baixa em arquivo temporário; valida SHA-256 do ZIP com o digest da release oficial, limita tamanho e redirecionamento HTTPS.
- Extrai em pasta de preparo ao lado da instalação, sem traversal, symlinks, nomes duplicados ou pacotes excessivos.
- Valida que `DUELTRACE-WebUI.exe` e `dueltrace-build.json` correspondem à versão, ID do workflow e commit publicados.
- Inicia helper PowerShell após conferência, fecha a janela do DUELTRACE, espera processo terminar, renomeia instalação atual como backup, posiciona pacote novo no mesmo diretório e reinicia o aplicativo. Em erro de troca, tenta restaurar a instalação anterior.
- Os perfis, ISOs, configurações e observações permanecem em `%LOCALAPPDATA%/ForbiddenMemoriesMultiMod`, fora da pasta de binários.
- Se existir backup de atualização anterior, recusa nova substituição automática em vez de apagar arquivos sem revisão; é necessário resolver/arquivar esse backup.
- Falha de rede/GitHub 403/limite API: informa motivo sem modificar a instalação.

**Aviso:** O SHA-256 protege contra corrupção/troca divergente do ativo publicado; não substitui assinatura de código e não prova que o binário é seguro. Apenas Releases do repositório oficial configurado são considerados. Nunca ignorar prompts de bloqueio do Windows.

## Limites reais

- Uma versão anterior à v0.8.5 **não pode ganhar esse código sozinha**; instalar a v0.8.5 manualmente uma vez após seu build público.
- Disponibilidade da publicação automática depende de o GitHub permitir `contents:write` ao job da CI e de o upload do asset efetivar seu `digest`.
- A troca e reinicialização precisam ser testadas em Windows real; testes simulados + CI comprovam a estrutura, não a UX final na máquina do jogador.
- Não mexe em fórmula RANK, scanner, biblioteca, fusões, drops, molduras, RAM/MIPS, nem desbloqueia mods sem binding.

## Próxima continuação

> Continue DUELTRACE v0.8.5, repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v085-preview-auto-update`. O botão de atualização agora contempla Preview não assinada com consentimento explícito, publicada por CI oficial em GitHub Releases, hash SHA-256, identidade SHA/Run ID no ZIP e substituição da instalação em helper separado com backup. Validar em Windows de verdade: publicação do release, descoberta da nova versão, download, verificação, relaunch, rollback, proteção contra versões antigas e locais sem permissão. Ainda é preciso instalar a primeira versão com esse sistema uma vez manualmente. Preservar fórmula RANK e bloqueio RAM por mod. Conferir SHA, PR, CI e testes antes de concluir. Próxima meta: validar RANK real no ePSXe em Remaster X15, FM13 e Original. Ao terminar, registrar versão, branch, commit, PR, CI, testes e pendências.
