# DUELTRACE — Atualizações pelo próprio aplicativo (Etapa 44)

## Comportamento preservado

O usuário continua com o mesmo controle **Atualizações → Atualizar agora**.
Ao receber um ZIP autorizado, o DUELTRACE:

1. Detecta uma versão superior ou uma Preview mais recente (build-id).
2. Verifica o repositório/tag oficial, commit completo, tamanho e SHA-256.
3. Baixa o pacote para o diretório temporário de dados do DUELTRACE.
4. Confere o `dueltrace-build.json` incorporado no ZIP (versão, run_id, SHA).
5. Fecha apenas o processo atual, substitui os arquivos gerenciados na
   **mesma pasta instalada**, reinicia o EXE e preserva os arquivos pessoais.
6. Se a troca ou o reinício falhar, restaura os binários anteriores e registra
   o resultado no log local. Não cria outra instalação nem altera a ISO.

O botão **não** faz instalações silenciosas sem clique do usuário.
O canal Alpha/Preview e o fluxo de instalação comercial permanecem separados
para evitar instalar pacote de uma edição sobre outra.

## Problema real — Repositório privado

GitHub REST sem autenticação normalmente responde `404` para um repositório
privado. Um aplicativo instalado **não herda o login do navegador**.
Por isso, o botão antigo pode não detectar a versão disponível, mesmo com
um ZIP publicado no GitHub privado.

A Etapa 44 adiciona um acesso **opcional**, só para o proprietário/testadores
que possuem acesso autorizado ao repositório:

- Tenta primeiro o acesso HTTPS público existente (sem mudança).
- Quando recebe `401`, `403` ou `404`, utiliza o **GitHub CLI autenticado
  localmente** para consultar somente as Releases de `guibatoni/appassist`.
- Para ZIP privado, faz download do arquivo exato usando a credencial local
  do GitHub CLI. O arquivo segue integralmente os mesmos testes de integridade
  e identidade incorporada do build.
- Nenhuma senha/PAT/segredo GitHub é embutido no EXE ou registrado no log.
  O processo não abre um login automaticamente e não envia ISOs ou dados RAM.
- Se o GitHub CLI estiver ausente/desatualizado/não autorizado, o DUELTRACE
  mostra uma orientação; não tenta baixar um pacote sem verificação.
- Para se proteger contra vulnerabilidade recente de arquivos via links
  simbólicos, o downloader privado exige **GitHub CLI 2.102.0 ou superior**.

### Configuração única no Windows do proprietário

1. Instale o GitHub CLI oficial (https://cli.github.com/).
2. Em um terminal Windows, execute `gh auth login` e selecione GitHub.com
   e a autenticação pelo navegador. Use **a conta com acesso ao repositório
   privado**. Nunca copie uma chave/PAT dentro do DUELTRACE.
3. Confirme com `gh auth status` (sem colar seus dados privados em mensagens).
4. Abra a Preview da Etapa 44 e use **Atualizações → Atualizar agora** nas
   próximas versões, sem baixar ZIP manualmente.

**A instalação atual anterior à Etapa 44 ainda não conhece esse método.**
Uma atualização inicial com essa mudança precisa ser instalada uma única vez
via ZIP oficial. Depois, a autenticação local permite voltar ao fluxo padrão.

### Limitações comerciais

O GitHub CLI **não concede acesso a clientes sem permissão ao repositório**
e não é um método apropriado de distribuição de uma edição vendida.
Para a versão comercial, será necessário configurar uma distribuição separada
que os compradores possam consultar, idealmente um repositório só de binários
públicos ou um serviço de distribuição autenticado com assinaturas e chaves
gerenciadas no servidor. Isso **não** requer abrir o código-fonte, mas a
publicação binária pública precisa ser decidida pelo proprietário.

**Não** inserir um PAT de acesso ao repositório privado no executável,
no instalador, nos arquivos JS ou em uma URL de download: compradores poderiam
extrair esse segredo e acessar o código-fonte.

## Critérios de QA

- Testes sem rede de listagem privada com `404` e GitHub CLI autorizado;
- Respostas inválidas, versão CLI vulnerável e ausência de autenticação;
- ZIP adulterado, tamanho/hash incorreto, limpeza do arquivo temporário;
- Fluxos de releases públicas preservados;
- Testes completos do Windows, Next.js, scanner, extração, instalador ZIP e
  Microsoft Defender antes de publicar nova Preview;
- Confirmar manualmente no Windows que a conta do proprietário tem acesso e
  que a atualização reinicia na pasta já instalada.

A release é publicada automaticamente pelo workflow existente ao aprovar o
push da branch `feature/dueltrace-v097-...`, sem novos botões e sem
novas pastas de instalação.
