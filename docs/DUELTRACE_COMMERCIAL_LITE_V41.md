# DUELTRACE Commercial Lite — Etapa 41: Gerenciador Batoni Dev (offline)

## Objetivo

Emitir licenças assinadas pelo proprietário usando uma interface Windows
sem terminal, hospedagem ou API. A Alpha continua gratuita para testes;
o instalador Commercial Lite **não está liberado para venda**.

## Executável administrativo

`BatoniDev-LicenseManager.exe` é um programa SEPARADO do aplicativo dos
compradores. Ele usa Tkinter nativo do Python já empacotado via PyInstaller.

### O que a interface faz

1. **Chaves e segurança:** gera no computador do proprietário o par Ed25519.
   A chave privada é armazenada **criptografada com uma senha** escolhida pelo
   proprietário, em `%LOCALAPPDATA%\BatoniDev\LicenseManager\secrets`.
   Somente a chave pública pode ser exportada. Nunca gere a chave privada no
   GitHub Actions, envie a clientes, ao ChatGPT ou ao repositório.
2. **Emitir licença:** importa `DUELTRACE-pedido-ativacao.json` enviado pelo
   comprador e exige identificar a compra e **confirmar manualmente pagamento**.
   Depois solicita a senha da chave privada, assina `DUELTRACE-Licenca.json` e
   deixa escolher onde salvar. Envie somente esse JSON ao comprador.
3. **Licenças emitidas:** lista identificador da compra, licença, prefixo do
   identificador pseudônimo do dispositivo e validade. Permite reenviar a
   **mesma licença original**, sem criar uma ativação extra.
4. **Verificar licença:** verifica assinatura Ed25519 de um arquivo recebido.
5. **Recuperar chave pública:** se o arquivo público se perder mas o privado
   criptografado ainda existir, a chave pública pode ser reconstruída pela
   senha. A chave privada não é recuperável se for perdida.

### Limites de emissão

- Limite LOCAL de dois dispositivos distintos por ID de compra.
- Pedidos repetidos e emissão repetida para o mesmo computador são recusados.
- Esse limite é controlado pelo histórico **somente no PC do proprietário**;
  outro gerenciador com histórico diferente não tem como consultar as emissões.
- Sem servidor, licenças offline **não podem ser revogadas remotamente**,
  bloqueadas por IP ou automaticamente ligadas a pagamentos Patreon.
- Reinstalar o app no mesmo PC mantém a licença no AppData.
- Ao trocar de PC, o comprador envia novo pedido; a Batoni Dev confere a
  compra e reemite manualmente conforme política de atendimento.
- Os IDs de dispositivo, mesmo com hash, são potencialmente dados pessoais:
  retenha o histórico pelo mínimo necessário e proteja o perfil Windows.

## Primeira configuração no PC do proprietário

1. Baixe e extraia `BatoniDev-LicenseManager-Windows-TESTE.zip` do artefato
   do CI/PR privado, **apenas após os testes**. A versão de teste não possui
   assinatura Authenticode.
2. Abra `BatoniDev-LicenseManager.exe` e vá em **Chaves e segurança**.
3. Clique em **Criar chaves privadas e públicas**, digite e confirme uma senha
   forte. A senha não é enviada a ninguém e não há recuperação automática.
4. Faça **backup offline e cifrado** da pasta
   `%LOCALAPPDATA%\BatoniDev\LicenseManager\secrets` e guarde a senha em
   local separado. Faça também backup de `ledger.json` e `issued\`.
5. Clique **Exportar chave pública**. Esta é a ÚNICA chave que deve ser
   incorporada ao compilador comercial, após passar pelas verificações finais.
6. Na guia **Emitir licença**, selecione um pedido enviado pelo comprador,
   informe ID da transação, confirme pagamento, emita o arquivo e envie o JSON.

### Chaves definitivas ainda não configuradas

O repositório mantém `PUBLIC_KEY_B64 = ""` intencionalmente, para bloquear
ativações comerciais até a chave pública de produção ser incorporada em uma
compilação revisada e assinada. A interface administrativa nunca gera uma
chave privada no CI. Não envie a chave privada nem a senha para configurar o
produto.

## Build manual de desenvolvimento (Windows)

Depois de baixar ou clonar o projeto e instalar Python 3.12:

```powershell
python -m pip install cryptography==50.0.2 pyinstaller==6.22.3
python -m unittest discover -s tests -p "test_dueltrace_license_admin*.py" -v
python -m PyInstaller --noconfirm --clean --onedir --noconsole --name BatoniDev-LicenseManager --paths scanner --paths tools/licensing tools/licensing/dueltrace_license_admin.py
```

O executável estará na pasta
`dist\BatoniDev-LicenseManager\BatoniDev-LicenseManager.exe`.

O workflow **Validar Gerenciador de Licenças Batoni Dev (Windows TESTE)**
compila e examina um ZIP do aplicativo com Defender; tenta disponibilizar o
ZIP no artefato privado `BatoniDev-LicenseManager-Windows-TESTE` por 7 dias.
Se o GitHub bloquear Artifacts por cota, o build poderá ser feito localmente.
O workflow não publica automaticamente uma Release comercial.

## Verificações e limitações antes da venda

- Testar interface com mouse/teclado e emissão real no Windows do proprietário,
  inclusive backup e recuperação de chaves. Testes de CI usam **chaves de teste**.
- Definir canal autenticado de atualização próprio do Commercial Lite: o
  atualizador da Alpha fica bloqueado na edição comercial.
- Validar assinatura digital Authenticode, SmartScreen, antivírus, instalação
  e funcionamento com ePSXe, RANK e ISOs reais.
- Revisar direitos de terceiros e licenciamento do material de Yu-Gi-Oh!:
  **não vender** sem a orientação jurídica adequada.
- Criar Política de Privacidade e suporte para troca de PC e incidentes.
- Confirmar as taxas por venda do Patreon e tributação. Infraestrutura sem
  servidor pago não significa operação totalmente sem custo.
