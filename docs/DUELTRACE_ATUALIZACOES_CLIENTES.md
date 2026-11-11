# DUELTRACE — atualizações Windows para clientes, sem GitHub Actions

O código-fonte do aplicativo permanece privado em `guibatoni/appassist`.
As releases públicas contêm **somente o ZIP Windows**, em
`guibatoni/dueltrace-releases`, e podem ser consultadas anonimamente pelo
aplicativo. **Clientes não precisam ter GitHub, instalar GitHub CLI ou digitar
tokens** para verificar/instalar atualizações.

## Kit com arquivos de um clique

Os quatro arquivos `.cmd` necessários, o assistente Windows, as verificações
necessárias e as instruções para quem usa a v53 estão documentados em
[DUELTRACE_KIT_WINDOWS_V58.md](DUELTRACE_KIT_WINDOWS_V58.md).

## Compilação e publicação pelo Windows do desenvolvedor

**O GitHub Actions NÃO é mais necessário para produzir nem publicar
atualizações.** O desenvolvedor executa o script local
`tools/release/publicar_cliente.ps1`, após revisar/commitar o código.
A compilação local inclui os recursos das etapas v54–v57 por estar na branch
encadeada de desenvolvimento.

Pré-requisitos no **Windows do desenvolvedor** (não no PC dos clientes):

- Git e um checkout limpo do repositório privado `guibatoni/appassist`.
- Python 3.12 com acesso a PyPI, Node.js 22 e npm.
- Windows 10/11, Windows SDK com `signtool.exe`, Microsoft Defender ativo e
  atualizado, internet para auditorias e carimbo de tempo da assinatura.
- Para **publicar**, certificado real Authenticode de editor confiável,
  com chave privada instalada em `Cert:\CurrentUser\My`.
- GitHub CLI autorizado **apenas para o desenvolvedor** (uma vez, `gh auth
  login`). O app de clientes nunca usa GH CLI ou tokens.

### 1. Build local apenas para desenvolvimento

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/release/publicar_cliente.ps1
```

O script verifica o código Git, executa todos os testes Python, instala
dependências fixadas, audita dependências web, compila a UI estática, empacota
com PyInstaller, verifica integridade e executa Microsoft Defender. O ZIP
experimental sem assinatura fica em
`dist/DUELTRACE-WebUI-Windows-Preview.zip`; **não deve ser distribuído
como release pública para clientes**.

### 2. Preparar a distribuição pública (ação única)

1. Criar **um novo repositório público**, exatamente
   `guibatoni/dueltrace-releases`, com README e branch `main`.
   **Não** tornar `guibatoni/appassist` público.
2. Instalar o certificado de assinatura Authenticode válido no armazenamento
   de certificados do Windows e anotar o Thumbprint (40 caracteres hex) e
   o Subject exato do editor.
3. No computador do desenvolvedor, executar `gh auth login` com autorização
   para **criar releases somente no repositório público de distribuição**.
   Se possível, usar credenciais de escopo mínimo.

### 3. Gerar e publicar a release assinada

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/release/publicar_cliente.ps1 -Publish -CertificateThumbprint "SEU_THUMBPRINT_40_HEX" -ExpectedPublisherSubject "CN=SEU_EDITOR"
```

O script compila o Windows localmente, assina e confere o EXE, executa as
auditorias e o Defender e publica somente o ZIP no repositório público.
A tag é `preview-v0.9.7-r<BUILD_ID>`, sendo `BUILD_ID` um identificador
numérico local em UTC. O arquivo `_internal/dueltrace-build.json` e as
notas da release incluem a versão, o ID do build e o SHA do commit privado.
É publicado SHA-256 do ZIP assinado. A mesma tag nunca é sobrescrita.

**Ao finalizar com sucesso**, o PowerShell imprime o endereço completo:

`https://github.com/guibatoni/dueltrace-releases/releases/download/<TAG>/DUELTRACE-WebUI-Windows-Preview.zip`

O link é válido **somente após a publicação**; não use endereço inventado.
O código-fonte privado não é enviado ao repositório público.

## Atualização dos computadores dos clientes

1. Cliente abre o DUELTRACE e clica em **Atualizações**.
2. O aplicativo consulta o repositório de releases público por HTTPS,
   sem autenticação.
3. Verifica tag, ID de build, SHA-256, tamanho, origem e identidade interna.
4. Após clique em **Atualizar agora**, baixa e instala **na mesma pasta**,
   preserva ISOs/dados e utiliza rollback caso o reinício falhe.

**Migração inicial obrigatória:** versões antigas (como a Preview v53)
ainda consultam o repositório privado e não sabem do canal público. É
necessário disponibilizar uma **primeira instalação manual**, com o updater
novo compilado neste processo. Só depois essas instalações passam a
atualizar-se pelo botão sem login.

## Segurança, privacidade e comercialização

- Não incorporar token do GitHub nem a chave de assinatura ao aplicativo.
- Não baixar/instalar Builds de GitHub Actions ou ROMs pelo atualizador.
- Se falta assinatura Authenticode, auditoria, Defender, acesso de publicação
  ou validação de origem, **não publicar**.
- Um ZIP em repositório público pode ser baixado por qualquer pessoa.
  Para vender acesso individual é necessário licenciamento de aplicativo
  ou servidor próprio com autenticação de compradores; isso é independente
  do atualizador.

O workflow automático antigo de compilação/publicação WebUI Windows foi removido.
Outros workflows legados do projeto são independentes do processo de atualização
para clientes; o fluxo de distribuição Windows é executado localmente.

O script local executa também `python -m pip_audit --local`, `npm audit`, testes
Python e verificação do build estático, além das análises do pacote Windows.
