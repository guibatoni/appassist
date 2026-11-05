# DUELTRACE — Atualização na mesma pasta e reinício automático

Esta alteração corrige o processo de atualização portátil e Preview para Windows, sem mudar fórmulas, RANKs, catálogo nem perfis de mods.

## Comportamento esperado

1. Usuário clica em **Atualizar agora**.
2. App baixa o ZIP oficial e valida URL permitida, SHA-256, identidade do build e versão, antes de alterar a instalação.
3. Arquivos de preparação ficam em `%LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\preview_updates` (caminho padrão). Nenhuma segunda pasta de instalação é criada ao lado do executável.
4. DUELTRACE fecha e o helper externo espera o processo terminar; se permanecer bloqueado, verifica o caminho exato antes de finalizar **somente** esse processo.
5. Mantém uma cópia de rollback em dados locais, troca apenas `DUELTRACE-WebUI.exe`, `_internal` e `LEIA-ME-SEGURANCA.txt` **dentro da mesma pasta**. Não altera pastas e arquivos do usuário.
6. Abre o mesmo caminho `DUELTRACE-WebUI.exe` e verifica se o processo segue em execução.
7. Limpa a pasta temporária e realoca para os dados locais apenas backups e pastas temporárias de versões antigas que correspondam aos padrões gerados pelo instalador anterior. Itens desconhecidos ficam intactos.
8. Se não conseguir substituir ou inicializar, tenta restaurar os arquivos anteriores e relançar a versão antiga. O log permanece em `preview_updates\\ultima-atualizacao.log`.

## Segurança e limites

A atualização pode levar alguns segundos com o programa fechado. Versões portáteis Preview não são assinadas digitalmente; não desabilitar o Windows Defender. O arquivo de rollback fica nos dados do aplicativo para recuperação, não em uma pasta vizinha à instalação.

O teste Windows usa um executável simulado e intercepta a função de reinício para não abrir outro aplicativo durante a suíte. Build, assinaturas/identidade, auditoria e empacotamento são verificados pelo GitHub Actions. Um teste de usuário real ainda é necessário para confirmar o comportamento no computador em uso.
