# DUELTRACE Commercial Lite — Etapa 39 (protótipo privado)

## Objetivo
Criar uma edição Windows com custo fixo de servidor **zero** para iniciar um
processo de comercialização futuro, preservando integralmente a Alpha e o
mecanismo atual de atualizações ZIP. Este PR NÃO habilita bloqueio por licença
na Alpha, NÃO publica um instalador comercial e NÃO autoriza vendas antes da
revisão dos direitos de terceiros.

## Modelo comercial econômico
- Venda avulsa, quando disponível, por plataforma que suporte produto digital
  sem mensalidade ao comprador (as plataformas podem cobrar taxas por venda).
- **NSIS** para montar um instalador por usuário sem solicitar administrador.
- **PyInstaller** atual preservado; sem Python/Node no computador do cliente.
- Cada cliente envia uma solicitação de ativação contendo apenas um identificador
  *pseudônimo* do dispositivo (SHA-256 com domínio DUELTRACE, calculado localmente).
- Batoni Dev emite manualmente um arquivo `license.json` **assinado Ed25519**.
- O aplicativo verifica a assinatura offline pela chave pública incorporada.
- O IP NÃO identifica a licença: muda com a rede, VPN e provedor.
- A proposta "até dois computadores" exige **duas licenças por dispositivo**
  emitidas manualmente sob o mesmo pedido; sem servidor não existe controle de
  número de ativações automático nem revogação online. Registre emissões em
  controle administrativo privado, fora do repositório.

## Limitações essenciais
- Licenciamento offline é um impedimento básico à cópia casual, não uma barreira
  perfeita contra modificações do programa, compartilhamento de executáveis
  alterados ou falsificação da hora local. Reemissão após trocar o hardware
  será atendida manualmente.
- A licença Ed25519 **NÃO** assina o executável Windows (Authenticode) e **NÃO**
  remove avisos do Microsoft Defender ou SmartScreen.
- Nunca desative o Defender, SmartScreen ou verificações de atualização para
  facilitar instalação.
- Não distribua dados de ROMs, saves, cartas, imagens ou material protegido no
  instalador. Avaliação legal sobre compatibilidade e direitos de marcas/arte
  **deve preceder qualquer venda**.
- A chave pública embutida continua vazia nesta etapa: nenhuma licença real pode
  ser ativada até criar o par definitivo offline e empacotar a chave pública.

## Workflow do dono (futuro, somente ambiente de teste)
Requer Python 3.12 e `pip install cryptography==50.0.2`.
Execute o gerador **em um computador controlado e desconectado** do GitHub.
Nunca rode a emissão da chave privada em CI, nem no computador do cliente.

```powershell
python tools/licensing/dueltrace_license_cli.py keygen --private C:\BATONI-SECRET\private.pem --public C:\BATONI-SECRET\public.txt
```

A chave privada é armazenada em PEM **criptografado por senha forte**.
Armazene o arquivo fora do projeto, com cópia de segurança segura. Copie
SOMENTE os 44 caracteres públicos de `public.txt` para
`scanner/dueltrace_commercial_public_key.py` antes de criar um build comercial
**quando o produto e os testes estiverem validados**.

No Windows do cliente de testes, gerar a requisição (não faz chamada de rede):

```powershell
python tools/licensing/dueltrace_license_cli.py request --output activation-request.json
```

O cliente fornece `activation-request.json` à Batoni Dev pelo canal seguro
acordado. Este arquivo tem hash pseudônimo persistente: trate-o como dado
pessoal potencial; não publique no GitHub.

No computador privado do dono:

```powershell
python tools/licensing/dueltrace_license_cli.py issue --private C:\BATONI-SECRET\private.pem --request activation-request.json --output issued-license.json
python tools/licensing/dueltrace_license_cli.py verify --public C:\BATONI-SECRET\public.txt --request activation-request.json --license issued-license.json
```

Na fase seguinte, a interface de ativação deverá importar o arquivo assinado,
validar dispositivo e salvar a licença em
`%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\commercial\license.json`.
Esta integração e o bloqueio de acesso são **pendentes**, para preservar a Alpha.

## Instalador NSIS de testes
1. Compile a WebUI/PyInstaller com a mesma revisão segura do CI. Não use ROMs.
2. Instale NSIS no computador Windows de desenvolvimento.
3. Execute o compilador NSIS apontando para `dist\DUELTRACE-WebUI`:

```powershell
makensis /DBUILD_DIR="C:\CAMINHO\DO\REPO\dist\DUELTRACE-WebUI" installer\dueltrace-commercial-lite.nsi
```

O arquivo de saída será **DUELTRACE-Setup-TESTE.exe**: somente para
testes de instalação/desinstalação em ambiente controlado. Instala por usuário
em `%LOCALAPPDATA%\Programs\DUELTRACE` ou usa o diretório já registrado
para a instalação anterior, sem criar outra cópia. A desinstalação elimina
os binários gerenciados; preserva as configurações, mods e arquivos pessoais
de AppData.

O instalador não foi assinado com Authenticode; ele NÃO faz parte da Release
Preview e não é publicado automaticamente.

## Critérios para avançar à Etapa 40
- Teste real de instalador, reabertura, atualização in-place e desinstalação
  no Windows 10/11 sem afetar dados, memory cards e ISOs pessoais.
- Aprovar CI Python e Windows, segurança de dependências, auditoria ZIP,
  Microsoft Defender e integração WebView2/ePSXe.
- Revisar tratamento de registros de vendas/identificação com LGPD.
- Validar juridicamente direitos sobre o produto e sua apresentação comercial.
- Criar tela de ativação amigável e fluxo de troca de computador, mantendo Alpha
  intacta; somente então decidir quando exigir licença na edição comercial.
