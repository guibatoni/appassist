# DUELTRACE — Segurança e privacidade dos clientes

Estado em novembro de 2026: **WebUI v0 é prévia experimental; não substitui a Alpha 0.6.6 oficialmente.**

## Dados acessados
- ISO/BIN escolhida explicitamente pelo usuário: leitura local e SHA-256, sem modificar a ROM.
- Mão no ePSXe: leitura de memória, sem escrever na RAM, Memory Card ou saves.
- Perfis, imagens extraídas e configurações armazenados em %LOCALAPPDATA%/ForbiddenMemoriesMultiMod.
- Nesta WebUI não há upload automático de ISOs, saves, cartas ou dados pessoais para o Vercel.
- O site público não possui acesso à memória do ePSXe.

## Proteções adicionadas
- Servidor HTTP apenas em 127.0.0.1; Host e Origin estritamente verificados.
- Bloqueia requisições cross-site, listagem de pastas, symlinks que escapem da pasta estática e caminhos perigosos.
- Headers de segurança: CSP, X-Frame-Options, CORP, Permissions-Policy e nosniff.
- Ponte Python expõe apenas métodos permitidos e exige uma credencial aleatória por sessão da janela local.
- As fusões e efeitos continuam segregados por perfil, com proveniência e sem inventar dados.
- Dependências Next.js/Python passam por auditoria de CVEs antes da distribuição.
- O Windows Defender examina o executável e o ZIP; se não estiver disponível ou se detectar ameaça, o pipeline bloqueia a publicação.
- Hashes SHA-256 do pacote e do executável são registrados junto a um relatório de auditoria.

## Limitações
Uma compilação bem-sucedida não garante segurança. Antivírus não detecta todas as ameaças.
SHA-256 prova integridade de bytes frente a um hash confiável, não autentica autoria.
**Assinatura digital Authenticode e testes com o ePSXe real ainda são necessários antes da distribuição comercial.**
Um aplicativo assinado também pode receber avisos do SmartScreen e precisar construir reputação.

## Checklist de lançamento
1. Revisar modificações de código e dependências; impedir merge sem CI de segurança.
2. Aprovar testes, análise de vulnerabilidades, inventário e antivírus atualizados.
3. Validar a WebUI no Windows com WebView2 e ePSXe reais.
4. Assinar o executável e o instalador e implementar atualizações autenticadas com rollback.
5. Conferir hashes e publicar changelog e procedimento de instalação seguro.
6. Verificar direitos sobre imagens e ativos de terceiros antes de comercializar.

**Nunca oriente usuários a desativar Chrome Safe Browsing, Defender ou SmartScreen para executar o DUELTRACE.**

## Incidentes e comunicação
Em caso de suspeita de malware ou vulnerabilidade, interromper distribuição, investigar, revogar eventuais credenciais expostas e avisar usuários afetados.
Para reportar vulnerabilidades, contate o mantenedor privadamente pelo GitHub; não publique senhas ou arquivos pessoais em Issues.
Estas medidas reduzem o risco, mas não representam garantia absoluta de segurança.
