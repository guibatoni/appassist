# DUELTRACE Windows — Política de distribuição confiável (v0.7.3)

## Situação atual
Em 03/11/2026, o Chrome apresentou **"Download perigoso bloqueado"** no ZIP do DUELTRACE WebUI gerado por GitHub Actions. Esse aviso NÃO é prova de malware, mas não pode ser ignorado como falso positivo sem investigação. A prévia é **não assinada**. Testes, Microsoft Defender e SHA-256 reduzem riscos e oferecem evidências, não uma garantia de segurança.

**Não peça a ninguém que desative Chrome Safe Browsing, Microsoft Defender, SmartScreen ou outros bloqueios para instalar este produto.**

## Proteções agora presentes na linha Preview
1. Suite de regressão Python, build Next.js, auditoria `npm audit` e `pip-audit` em CI.
2. Verificação de Defender sobre a pasta de distribuição e o ZIP, com falha fechada.
3. `tools/security/audit_windows_archive.py`: compara o SHA-256 de cada entrada com a pasta de build examinada; falha para travessia de caminhos, entradas duplicadas, arquivos inesperados, segredos/arquivos comerciais da ROM ou divergências de bytes.
4. `tools/security/gate_windows_package.ps1`: gera `SHA256SUMS.txt` e `SECURITY-REPORT.json` incluindo **status real da assinatura**. O parâmetro `-RequireSignature` impede a aprovação de uma release pública sem Authenticode válido e sem o assunto exato do certificado do editor.
5. As prévias exibem `LEIA-ME-SEGURANCA.txt` e o nome de artefato **Unsigned-Security-Scanned**. Nenhum desses rótulos assegura ausência de malware.
6. App mantém ISO, perfis e leitura de RAM localmente, sem uploads implícitos.

## Critérios OBRIGATÓRIOS para lançar ao público
- Auditar código e dependências, revisar comportamento de leitura de memória e dados locais e evitar componentes desnecessários.
- Executar CI integral, verificar alertas de antivírus em Windows reais e avaliar resultados independentes sem enviar informações privadas ou ISOs.
- **Assinar o EXE (e um instalador, caso exista) com Authenticode usando certificado emitido por autoridade reconhecida**. Certificados autoassinados não resolvem confiança de consumidores.
- No Brasil, verificar a elegibilidade dos provedores. A Microsoft documenta limites geográficos para Artifact Signing; alternativa comercial é certificado OV de uma AC reconhecida ou distribuição adequada pela Microsoft Store. Não presumir que Artifact Signing esteja disponível em conta brasileira.
- Guardar credenciais e chaves fora do GitHub. Preferir serviço de assinatura em nuvem/HSM, integração controlada no CI, identidade estável e carimbo de tempo. Nunca enviar PFX, chave ou senha por chat, GitHub ou ZIP.
- Executar o *gate de publicação* após a assinatura: gerar o ZIP somente DEPOIS de assinar o executável e verificar novamente o pacote e as assinaturas. Exemplo de invocação (assunto abaixo é ilustrativo, substituir pelo assunto exato obtido do certificado real):

```powershell
./tools/security/gate_windows_package.ps1 `
  -PackageDirectory dist/DUELTRACE-WebUI `
  -ZipPath dist/DUELTRACE-WebUI-Windows.zip `
  -OutputDirectory dist/security `
  -RequireSignature `
  -ExpectedPublisherSubject 'CN=Batoni Dev, O=EMPRESA_VERIFICADA, C=BR'
```

- Após aprovação, publicar uma **GitHub Release oficial** (não somente artefato temporário do Actions), com changelog, certificado do editor, SHA-256 e instruções de instalação; tornar a atualização automática autenticada/segura antes de habilitá-la.
- Se ainda surgir alerta, determinar a categoria exata no Chrome e submeter evidências aos fornecedores. O Chrome Safe Browsing usa classificações diferentes de Defender/SmartScreen. Uma assinatura também pode levar tempo para construir reputação.

## O que não foi feito
- **Nenhum certificado Authenticode foi adquirido ou configurado**; o EXE gerado por esta branch continua não assinado.
- Não foi feita análise independente multimecanismo do build final por consultoria ou por navegador Google.
- Não há liberação pública/comercial nem promessa de eliminação de todos os avisos.
- Não vamos alterar extensão, compactar com senha, ofuscar nem instruir usuários a burlar verificações como substituto da correção real.

## Diagnóstico de um bloqueio relatado
Registre de forma privada: URL original do GitHub, SHA-256 do ZIP, versão do Chrome, captura completa do aviso e, se disponível, detecção do antivírus/nome da ameaça. Não solicite dados pessoais, arquivos ISO, senhas ou tokens. Se for confirmado um falso positivo após validação, siga os procedimentos oficiais de recurso dos provedores.

## Fontes oficiais
- Google Chrome: https://support.google.com/chrome/answer/6261569?hl=pt-BR
- SmartScreen e reputação: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- Opções de assinatura: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- Análise de arquivo Microsoft: https://www.microsoft.com/en-us/wdsi/filesubmission

## Próximo passo técnico
Providenciar identidade editorial/certificado, integrar assinatura no CI **com credenciais protegidas**, verificar assinatura antes de publicar releases e realizar testes em Windows reais com proteção ativa.
