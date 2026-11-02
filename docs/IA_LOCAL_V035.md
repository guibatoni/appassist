# IA local opcional — MultiMod v0.3.5

A Biblioteca de Mods pode utilizar um modelo de linguagem **rodando no próprio computador** por meio do [Ollama](https://ollama.com/) para *sugerir investigações* sobre o formato de ROMs ainda desconhecidas.

**Segurança:** a IA não recebe a ISO/BIN completa, não altera o jogo e **nunca** marca uma sugestão como dado verificado. O relatório enviado ao endpoint local contém hash, metadados de arquivos e offsets candidatos extraídos pelo scanner. Dados ainda não confirmados continuam indisponíveis no overlay.

## Preparação (uma vez)
1. Instale o Ollama para Windows pelo site oficial.
2. Abra o Terminal e obtenha um modelo compatível (exemplo):
   `ollama pull qwen2.5:3b`
3. Confirme que o Ollama está em execução; a API local padrão responde em `http://127.0.0.1:11434`.
4. Atualize o launcher pelo GitHub para **v0.3.5**.
5. Se ainda não integrou a Biblioteca, feche o Assistente e execute `app/INTEGRAR_BIBLIOTECA_MODS.bat` uma vez. O programa faz backup antes de modificar a inicialização.

## Utilização
1. Abra **Biblioteca de Mods** no overlay pelo botão ou atalho **Ctrl+Shift+M**.
2. Importe uma ISO/BIN ou escolha uma pasta a monitorar.
3. Selecione um perfil importado.
4. Use **Investigar estrutura** para inspeção determinística.
5. Use **IA local: investigar** para pedir hipóteses sobre as evidências.
6. Caso queira análise automática, marque **IA automática (local)**. Padrão: desativado.
7. Revise as sugestões salvas em `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\investigacoes\*.ia.json`.
8. Só ative o perfil após validar os recursos confirmados e certificar-se de que a mesma ROM está aberta no ePSXe.

## Modos de operação
- **Sem Ollama:** scanner, Biblioteca, perfis e validação continuam ativos.
- **Com Ollama:** a IA explica inconsistências e sugere quais offsets/tabelas investigar.
- **IA com comportamento automático:** apenas após o usuário marcar a opção, os *novos mods* analisados podem ser enviados à API local. Nenhum arquivo binário é transmitido.

## Limitações
- Não é um modelo treinado especificamente para Forbidden Memories.
- A detecção de fusões, ranks e fórmulas inéditas ainda exige um parser novo ou confirmação por testes reais.
- A opção IA local requer que o usuário instale e inicialize o Ollama e o modelo selecionado.
- O servidor é **fixo em 127.0.0.1**; não usa API externa. Se um programa de terceiros controlar o serviço local, aplicam-se as políticas desse programa.
- Relatórios são sugestões; **não inserem registros** no catálogo confirmado.
- Reiniciar o overlay ainda pode ser necessário para redesenhar componentes legados.
