# DUELTRACE — Kit de compilação Windows (v58)

O código e o instalador já estão reunidos na branch
`feature/dueltrace-v097-final-click-fusions-local-updates-v58`
do repositório **privado** `guibatoni/appassist`.

**Importante:** os arquivos deste kit são scripts de construção/distribuição.
O executável `DUELTRACE-WebUI.exe` não é possível de produzir em um ambiente
Linux porque o pacote é gerado por PyInstaller + pywebview/WebView2 no Windows.

## Arquivos criados

| Arquivo | O que faz |
| --- | --- |
| `01_VERIFICAR_AMBIENTE_WINDOWS.cmd` | Verifica Windows, Python 3.12, Git, Node 22 e npm |
| `02_GERAR_DUELTRACE_COMPLETO.cmd` | Compila a aplicação completa para Windows, testa e gera ZIP **local** |
| `03_PREPARAR_CANAL_PUBLICO.cmd` | Pede confirmação para criar **apenas** `guibatoni/dueltrace-releases` público |
| `04_PUBLICAR_DUELTRACE_WINDOWS.cmd` | Escolhe certificado, compila, assina, examina e publica o ZIP público |
| `tools/release/assistente_windows.ps1` | Motor interativo dos quatro botões |
| `tools/release/publicar_cliente.ps1` | Motor de compilação/assinatura/publicação, independente do GitHub Actions |
| `tools/security/AVISO-ATUALIZACAO-CLIENTES.txt` | Aviso incluído no ZIP público e aceito pelo atualizador |
| `tests/test_dueltrace_windows_build_kit.py` | Contratos do build Windows e do publicador |

## Compilar no seu computador

1. Tenha o repositório privado clonado no Windows e abra uma cópia **limpa**
   da branch integrada v58, sem arquivos modificados não commitados.
2. Instale Git para Windows, Python **3.12** e Node.js **22**.
3. Clique duas vezes em `01_VERIFICAR_AMBIENTE_WINDOWS.cmd`.
4. Clique duas vezes em `02_GERAR_DUELTRACE_COMPLETO.cmd`.
5. Após **todos** os testes e auditorias, o ZIP completo será criado em
   `dist/DUELTRACE-WebUI-Windows-Preview.zip`.

O ZIP local é um build de desenvolvimento **sem assinatura**. Não o distribua
a clientes como release pública. Ele inclui todos os módulos do DUELTRACE
da branch v58 e os dados estáticos da interface, **não** inclui ISOs.

## Configurar atualizações sem login para os clientes

6. No computador do desenvolvedor, instale GitHub CLI e autorize sua conta
   (`gh auth login`). Essa autenticação nunca é solicitada aos clientes.
7. Clique em `03_PREPARAR_CANAL_PUBLICO.cmd`. O assistente exige que você
   digite **CRIAR** e cria `guibatoni/dueltrace-releases` como repositório
   público **novo e separado**. Não altera a visibilidade de `appassist`.
8. Instale um certificado válido de assinatura de código Authenticode com
   chave privada em `Cert:\CurrentUser\My` e o Windows SDK.
9. Clique em `04_PUBLICAR_DUELTRACE_WINDOWS.cmd`. Escolha o certificado.
   O processo recompila, audita dependências, verifica Defender e assinatura
   e publica **somente o ZIP** no repositório público.
10. No fim da publicação, o assistente imprime o **link direto real**.
    O download do cliente será sem login no GitHub.

**Não há como obter link novo antes de compilar e publicar.**

## Migração de quem usa a v53

Uma pessoa com v53 precisa instalar **uma única vez** a nova versão compilada
com o canal de atualizações públicas, preservando a pasta de dados e as ISOs.
As versões seguintes poderão ser instaladas pelo próprio botão **Atualizar
agora**, sem conta GitHub. O ZIP público tem o arquivo
`LEIA-ME-ATUALIZACAO.txt`; o instalador já aceita esse arquivo, atualiza os
componentes gerenciados, preserva arquivos pessoais e faz rollback em falha.

## Limitações

- O repositório público ainda precisa ser criado pelo proprietário.
- O certificado de editor precisa ser fornecido pelo proprietário.
- Os clientes podem baixar um ZIP público mesmo sem ter comprado o produto.
  Controle de uso pago exige licença do aplicativo, separado do download.
- Não desative o Microsoft Defender ou o SmartScreen para tentar publicar.
- O kit não contém executável pronto, ROM ou código-fonte distribuível.
