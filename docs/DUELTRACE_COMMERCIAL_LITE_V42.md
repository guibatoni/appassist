# DUELTRACE Commercial Lite — Etapa 42: Design Batoni Dev unificado

## Objetivo
Aplicar ao Gerenciador de Licenças Batoni Dev a **mesma identidade visual do DUELTRACE** sem migrar segredos para HTML/WebView ou modificar a lógica de segurança.

## Design utilizado
As cores são exatamente as declaradas em `web/app/globals.css`:

| Token | Valor | Uso |
|---|---|---|
| Fundo | `#040a1a` | Janela |
| Painel | `#081530` | Cartões |
| Painel forte | `#0b1c3d` | Entradas e ações |
| Bordas | `#1b3f78` | Contorno e separadores |
| Ciano | `#38c8ff` | Seleção, títulos secundários |
| Dourado | `#f5b83d` | Destaques, botões principais |
| Texto | `#e6f0ff` | Conteúdo principal |
| Atenuado | `#8ea3c7` | Ajuda e descrições |

A janela usa controles internos de minimizar, maximizar e fechar, logotipo
triangular do DUELTRACE, barra superior personalizada, sidebar e painéis
arredondados. A interface foi refeita com **CustomTkinter 6.0.0**, que tem
licença permissiva e não exige servidor. Os diálogos de confirmação e senha
seguem o mesmo tema; não são telas de navegador.

## Funcionalidades preservadas
- Emissão de licenças Ed25519 com senha e confirmação de pagamento.
- Leitura e validação de pedidos JSON.
- Histórico e busca de licenças locais.
- Restrição de até dois dispositivos distintos por compra.
- Reenvio do arquivo original e verificação de assinatura.
- Geração de chave privada criptografada e exportação apenas da chave pública.
- Pasta local no perfil Windows, fora da instalação e do repositório.

## Segurança e distribuição
O processo principal ainda usa Python nativo e o gerenciador **não** expõe
APIs locais, HTML ou chaves pela rede. A assinatura privada continua ausente
do executável e do GitHub, e os testes criam apenas chaves temporárias.

O gerenciador e o DUELTRACE Alpha são aplicativos distintos. Não há fusão
com a distribuição do cliente, nenhuma modificação em dados de usuários ou
mudança em fórmulas e leituras de ISOs.

O build Windows usa PyInstaller `--onedir` e `--collect-all customtkinter`
para incluir recursos do tema. O teste gráfico automatizado abre a GUI,
percorre as três abas e fecha, sem gerar chaves nem assinaturas.

## Primeiro uso
1. Baixe o **BatoniDev-LicenseManager-Windows-TESTE.zip** da Release privada
   associada ao PR desta etapa, se o CI estiver aprovado.
2. Extraia **toda** a pasta; execute `BatoniDev-LicenseManager.exe`.
3. Na aba **Chaves e segurança**, gere o par definitivo somente no seu
   computador e proteja o arquivo criptografado e a senha com backups separados.
4. Exportar apenas a **chave pública** para o futuro build comercial.
5. Não publique a chave privada ou o arquivo de histórico de compradores.

## Pendências reais para venda
Este é um **redesign testável do gerenciador**, não o lançamento comercial:
o instalador do cliente ainda aguarda uma chave pública de produção,
canal de atualização comercial, assinatura Authenticode, testes manuais no
Windows e revisão legal de marcas e imagens de Yu-Gi-Oh!.

Não desative Defender ou SmartScreen. O executável administrativo TESTE
permanece sem assinatura Authenticode; não é destinado aos compradores.
