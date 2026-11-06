# DUELTRACE — Etapa 27: sincronização remota privada (opt-in)

**Estado:** implementação em branch isolada, dependente de CI + teste Windows real + configuração do usuário. Não é ligação direta desta conversa à RAM do Windows.

## Arquitetura

- O motor anterior de Live Diagnostics, que coleta a mão, LP, ID candidato e status RANK, permanece local e sem mudanças no formato-base.
- A nova camada `scanner/dueltrace_private_evidence_sync.py` aceita somente `https://api.github.com` e repositórios GitHub cujo metadado `private` é explicitamente verdadeiro; recusa qualquer repositório público.
- O usuário cria um **repositório privado separado** do `appassist` e um fine-grained PAT com permissão **Contents: Read and write** somente para esse repositório (não para a conta toda).
- A configuração acontece em **Biblioteca de Mods → DUELTRACE Live Diagnostics → Sincronização privada de evidências**. O token é digitado apenas no app e protegido no PC pelo Windows DPAPI por usuário. Não colocar tokens nesta conversa, no GitHub do projeto ou em .env versionado.
- Depois do clique explícito **Verificar privacidade e ativar**, os relatórios somente são enviados **se o diagnóstico também estiver iniciado**. Durante a coleta, envio em intervalos de aproximadamente 60s, e uma última tentativa ao parar a sessão.
- Gravações em `reports/<fingerprint-de-12-hex>/<id-sessao-16-hex>.json` no repositório privado. O mesmo arquivo da sessão é atualizado, não misturando sessões.
- Envio não bloqueia a leitura de RAM. Erros de rede não interrompem o jogo. A UI mostra último envio e erro resumido.
- **Desativar e apagar credencial local** bloqueia novos uploads e apaga o token local; não remove arquivos já publicados. Para revogar acesso no GitHub, revogar o PAT e gerenciar o repositório privado. Um envio iniciado antes da desativação ainda pode terminar.
- Não existe serviço HTTP escutando na máquina, abertura de portas nem controle remoto. Somente conexão HTTPS *de saída*.

## Dados enviados / dados NÃO enviados

Envia somente o JSON já saneado do `LiveDiagnosticsRecorder.export_json()`, com validação adicional estrita, limite de 140KB e campos numéricos/estados permitidos: IDs da mão, LP, ID candidato de adversário, resultados já observados de RANK e contadores/estados de sonda.

**Não envia:** ISO/BIN, ROM ou bytes do executável, imagens, arquivos de cartas/artes, RAM bruta, endereços de memória, PID, caminhos do Windows, tokens, chaves, histórico livre de conversas. Nenhum arquivo do jogo entra no GitHub privado automaticamente.

## Relação com o ChatGPT

O repositório de evidências é remoto, mas **não é uma API direta desta conversa**. O usuário precisa conceder acesso desse repositório ao GitHub conectado ao ChatGPT; então o assistente pode buscar arquivos via conector quando o usuário pedir uma análise. Isso não cria acompanhamento 24h, conexão direta ao computador, análise contínua sem novos turnos nem envio automático de mensagens.

## Segurança e limitações

- API GitHub fixa por código, TLS com verificação padrão e redirects bloqueados para impedir vazamento do PAT para outro host.
- A cada envio, a API verifica se o destino é privado (inclusive se alguém mudou sua visibilidade).
- Apenas o repositório escolhido recebe o JSON, e o token deve ter permissão de conteúdo somente nele.
- A sincronização não valida um adversário apenas por byte estável, não autentica qual ISO está aberta dentro do ePSXe e **não resolve automaticamente** ID→bloco, pools de drops, RANK ou fusões.
- A Biblioteca de 722 cartas, suas artes e a leitura de mão permanecem intocadas.

## Como configurar (depois que a Preview da Etapa 27 for aprovada)

1. Crie um repositório GitHub privado vazio, por exemplo `seu-usuario/dueltrace-evidencias`, separado do `appassist`.
2. Em GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens, selecione apenas o repositório privado e Contents **Read and write**. Escolha expiração curta e mantenha o token em segredo.
3. Na versão Etapa 27, Biblioteca de Mods → Live Diagnostics → Sincronização privada: digite `usuario/repositorio` e cole o token *apenas no aplicativo*. Marque o consentimento e clique **Verificar privacidade e ativar**.
4. Inicie um diagnóstico com o GOG ativo no ePSXe. Em ~60s ou ao parar, verifique o status de sincronização na UI.
5. No GitHub, confirme que `reports/` existe no repositório privado. Conceda ao conector GitHub do ChatGPT acesso a esse repositório se ainda não tiver. Na conversa, pode solicitar: “Leia o relatório mais recente no meu repositório privado de evidências e continue a análise do DUELTRACE.”

**Não foi criado nem habilitado automaticamente nenhum repositório privado de dados, token ou conexão remota nesta etapa.** Isso depende da ação do usuário.

## Próximo escopo de engenharia reversa

Primeiro validar o canal e a identidade de sessão. Depois acrescentar **eventos comprovados de início/término de duelo e identificação contextual do adversário** quando houver evidência de ROM/MIPS, ao invés de publicar números estáticos. Para drops e fusões, o parser de bytes reais da ISO continua essencial. Nunca ativar pools ou fusões só por frequência observada.
