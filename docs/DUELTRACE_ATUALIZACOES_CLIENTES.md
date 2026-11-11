# Atualizações para clientes — DUELTRACE (Windows)

## Objetivo

Todo usuário de um DUELTRACE instalado poderá clicar em **Atualizações → Atualizar agora** para baixar um ZIP verificado e substituir os arquivos do aplicativo na **mesma pasta**, com reinício e rollback. Não será necessário ter conta no GitHub, instalar GitHub CLI ou receber acesso ao repositório privado `guibatoni/appassist`.

A partir desta etapa o aplicativo consulta **apenas** o repositório público de distribuição binária `guibatoni/dueltrace-releases`. O repositório de código-fonte original continua privado. O canal de distribuição publica somente pacotes Windows e notas de versão; **não** publica ISOs, arquivos de clientes, relatórios de RAM, chaves privadas ou repositórios de desenvolvimento.

## Preparação necessária pelo proprietário

1. Criar `guibatoni/dueltrace-releases` como repositório **público**, contendo inicialmente apenas um README (branch `main`). O nome do repositório deve ser exato, pois a origem está fixada no aplicativo para evitar redirecionamentos suspeitos.
2. No repositório **privado** `guibatoni/appassist`, configurar uma Environment chamada `customer-release`, idealmente exigindo aprovação manual do proprietário.
3. Adicionar uma credencial **fine-grained** do GitHub em Actions Secrets, sob o nome `DUELTRACE_PUBLIC_RELEASE_TOKEN`, com acesso **somente** ao repositório `dueltrace-releases` e permissão Contents: Read and write. Não colocar tokens no executável, README ou arquivos rastreados.
4. Providenciar certificado real de assinatura de código Authenticode, emitido por uma autoridade confiável. No repositório **privado**, definir os Secrets `DUELTRACE_CODESIGN_PFX_BASE64` (PFX em base64) e `DUELTRACE_CODESIGN_PFX_PASSWORD`. Definir a Actions Variable `DUELTRACE_EXPECTED_PUBLISHER_SUBJECT` com o Subject exato do certificado. Não usar certificado autoassinado para distribuição a clientes.
5. Garantir que o GitHub Actions Windows esteja funcionando, inclusive auditoria da instalação, antivírus e validação do arquivo (o workflow atual estava falhando antes de iniciar o runner). Gerar uma Preview privada com workflow **concluído com sucesso** e release privada correspondente.
6. Após revisar e integrar o código, executar manualmente o workflow `Publicar atualizacao DUELTRACE para clientes` usando a tag completa da Preview privada aprovada. O processo verifica run/commit, ZIP e SHA-256; assina o EXE, reempacota, audita com Microsoft Defender, verifica o editor e publica apenas o ZIP **assinado** no repositório público.

A publicação **falha e não distribui nada** se qualquer um desses requisitos estiver ausente. O pipeline não publica automaticamente um PR, um build com falha ou um executável sem assinatura.

## Funcionalidade no aplicativo

- Verificação anônima em `https://api.github.com/repos/guibatoni/dueltrace-releases/releases`, respeitando HTTP/HTTPS, URL, tamanho, digest SHA-256 e origem fixa.
- Pré-releases usam tags `preview-vX.Y.Z-rBUILD`; as notas devem incluir uma única linha `Build BUILD | Commit SOURCE_SHA | SHA-256 ZIP: DIGEST`. O commit identificado é o da compilação **privada**, que não existe no repositório público.
- O ZIP contém `_internal/dueltrace-build.json` com versão, ID do build e SHA correspondentes aos metadados assinados da release.
- Comparação de versão/build evita retrocesso e instalações repetidas. Releases estáveis e Previews são distinguidas. O botão único prefere ZIP estável válido quando aplicável.
- Download e instalação acontecem apenas após clique explícito; ZIP é validado antes da troca. Instalação na pasta atual, sem apagar ISOs ou dados locais, com rollback em falhas.

## Duas limitações importantes

**Distribuição de binário público:** qualquer pessoa na internet conseguirá baixar o ZIP do repositório público, mesmo sem ter comprado o produto. Se a venda deve ser restrita a assinantes/compradores, será necessário **licenciamento validado pelo aplicativo** ou um servidor de downloads autenticado por licença. Um GitHub token universal embutido no aplicativo não é seguro.

**Atualização inicial:** uma versão já distribuída que somente consulta `guibatoni/appassist` **não passará magicamente a usar o novo canal**. Esses usuários precisarão instalar **uma vez** uma versão do DUELTRACE que já contenha o novo atualizador. Depois disso, as futuras atualizações poderão vir pelo botão normal, sem acesso ao GitHub privado.

Enquanto a release pública inicial, o certificado e a infraestrutura de publicação não estiverem configurados, **não anunciar que as atualizações de clientes estão ativas**.
