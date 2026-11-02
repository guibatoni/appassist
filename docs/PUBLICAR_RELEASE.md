# Publicar a primeira atualização pela internet

## 1. Enviar o código-fonte (uma única vez)
Baixe o pacote **Codigo_Fonte_AppAssist_Pronto_para_GitHub.zip** fornecido na conversa do ChatGPT.
Extraia a pasta `appassist-source` no Windows e execute `PUBLICAR_GITHUB.bat`.
O script exige **Git for Windows**, autenticação no GitHub e faz commit/push para `main`.

Verifique se agora existem no repositório os arquivos `launcher.py`, `launcher_core.py`, `tools/criar_patch.py`, `app/assistente_x15.py` e `tests/test_launcher.py`.

## 2. Publicar Release v0.3.1
Abra **Actions → Publicar patch oficial → Run workflow**. Preencha:
- Branch: `main`
- versao: `0.3.1`
- novidades: `Primeira atualização oficial do Assistente MultiMod.`

O workflow executa os testes, gera `patch.zip` contendo **somente arquivos de código permitidos da pasta app/**, valida o manifesto e publica a Release `v0.3.1` com **dois anexos obrigatórios**:
- `patch.zip`
- `update-manifest.json`

**Não crie a Release manualmente sem esses anexos.**

## 3. Testar o launcher
No launcher atualizado (v0.3), informe o repositório `guibatoni/appassist`, clique em **SALVAR**, depois **VERIFICAR VERSÃO** e **ATUALIZAR PELO GITHUB**.
Se o Assistente estiver aberto, autorize o encerramento e a reinicialização após aplicar o patch.

Não feche o ePSXe e não altere ISO, Memory Card ou saves. Os dados do jogo, perfis, imagens e saves não são publicados no GitHub.

## Atenção à numeração
O **launcher v0.3** é o aplicativo que instala as atualizações; a Release **0.3.1** é a versão do *pacote de código do assistente* e do estado de atualização `launcher_state.json`.
O patch não substitui o executável/arquivo `launcher.py` fora de `app/`: para atualizar o próprio launcher usamos um instalador de migração separado.

## Limites atuais
- A primeira Release instala/refresca apenas o **código**: dados de cartas, texturas e catálogos continuam os da instalação existente.
- A compilação independente de Python e a assinatura de origem do editor ainda não estão implementadas.
- A verificação SHA-256 protege a integridade do arquivo baixado, mas não substitui assinatura digital.
