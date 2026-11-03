# DUELTRACE Alpha v0.6.3 — Fusões, artes, efeitos, ePSXe e HUD

## Objetivo
O usuário abre o DUELTRACE, importa ou seleciona uma ISO/BIN local, ativa o perfil e pode jogar pelo ePSXe. O objetivo comercial permanece restrito às abas Início, Biblioteca de Mods, Biblioteca de Cartas e Fusões.

## Fusões — importação automática segura
O extrator já decodifica o formato WA_MRG de 7 bancos com índices uint16 e receitas compactadas de 10 bits, conhecido para Forbidden Memories. Antes desta atualização, a investigação do DUELTRACE não salvava o relatório **completo** no caminho utilizado pelo perfil. Agora:
1. Para cada SHA de ISO, o scanner reexecuta a investigação quando o schema muda e salva `investigacoes/<SHA>.fusoes.json`, incluindo todas as receitas.
2. O importador confere que são 7 bancos decodificados, 7 assinaturas idênticas, sem conflitos, contagens e SHA-256 de receitas coerentes, e que o arquivo original não mudou.
3. Somente com o catálogo de 722 cartas validado o resultado entra em `fusion_recipes`, com `validation=extraida_sete_bancos_consistentes`.
4. A funcionalidade de fusões é habilitada no perfil e o ponteiro de revisão do perfil ativo é incrementado para sincronizar assistente/overlay.
5. Fusões individualmente observadas em duelo continuam marcadas como observadas; reanalisar a ISO não deve apagar essas confirmações.
6. A aba Fusões oferece busca e paginação de 250 resultados. Não é necessário carregar 23 mil linhas de uma vez no Treeview.

**O que NÃO acontece:** a IA Ollama não assina nem confirma receitas, sete bancos iguais não são prova individual de gameplay, e ROMs divergentes não recebem fusões de outro mod.

## Artes — layout e diagnóstico
Para o Remaster X15 conhecido, a auditoria anterior documentou 722 imagens originais de 102 × 96, 8bpp e paleta PS1 BGR555, em blocos de 7 setores por carta a partir do setor interno 722 do arquivo WA_MRG.MRG.

O parser foi revisado para versão 2: força nova tentativa dos mods cujo cache anterior marcou falha, valida IDs 1..722 únicos, identifica prefixos curtos e descarta conjuntos quase totalmente uniformes. O método preserva a imagem BIN/ISO original e exporta PNGs em AppData. Fontes de mods diferentes continuam exigindo confirmação visual.

## Efeitos — investigação honesta
Não temos evidência suficiente para mapear automaticamente cada efeito customizado no binário Remaster X15. A Alpha cria `investigacoes/<SHA>.efeitos-auditoria.json`, listando arquivos candidatos, possíveis strings legíveis e trechos do banco de glifos de Forbidden Memories. **Nenhum texto é associado automaticamente a uma carta sem vínculo explícito de ID/origem**. Quando houver DTEFFECT.JSON interno ou manifesto local com SHA correto, a lógica anterior segue funcionando.

Se o autor do mod fornecer `Guia_Mecanicas_Remaster_PT-BR.txt` ou outro guia, é possível investigar uma associação comprovada no desenvolvimento posterior; não inclua dados de uma versão antiga como fatos da versão 1.2.1.

## ePSXe — iniciar jogo opcional
1. Abra Biblioteca de Mods; clique em **Selecionar ePSXe.exe** e escolha o executável da instalação existente.
2. Selecione uma ISO/BIN da sua lista e clique **Ativar perfil**.
3. Clique em **Iniciar mod no ePSXe**. O aplicativo chama `ePSXe.exe -nogui -loadiso <caminho da ISO>` como argumentos separados, sem abrir CMD.
4. Se quiser abrir ao ativar o perfil, marque **Iniciar após ativar o perfil**. Por padrão essa opção vem desligada.
5. A imagem precisa ser a do perfil ativo e não ter sido alterada após a análise. Não redistribuímos emulador, ROMs, BIOS ou memory cards.

Essa integração foi confirmada somente por simulação de subprocess e documentação do ePSXe, não pela execução real do jogo no PC do usuário. O DUELTRACE não confirma automaticamente que um duelo foi iniciado nem altera saves.

## HUD e desempenho
- Painéis e botões em Tk Canvas agora desenham gradientes e bordas com cantos arredondados por geometria circular.
- O tema preserva as cores azul-marinho, ciano e dourado; o resultado ainda depende de validação visual em Windows/DPI.
- Scanner usa worker em background **durante a execução do app**, cache local por SHA e reanálise manual. Não é um serviço remoto.
- Dados de arte, efeitos, drops e fusões continuam separados por SHA.

## Testes e limitações
CI Windows valida sintaxe e regressão com bancos de fusão sintéticos, conflitos, idempotência, persistência de confirmação manual, simulação de ePSXe, auditoria de efeitos, GIF/PNG/ICO e GUI. As ISOs reais dos três mods e o executável ePSXe instalado não estavam disponíveis no ambiente de build. Por isso a Alpha 0.6.3 é candidata a teste local, **não** versão final perfeita ou pronta para venda.

Checklist da próxima validação real: obter o relatório de diagnóstico de cada mod, contar as imagens PNG salvas, comparar 10 artes de IDs distintos às exibidas no jogo, testar amostras aleatórias de fusões sugeridas, identificar os efeitos em manual/execução do mod e verificar a abertura via ePSXe.
