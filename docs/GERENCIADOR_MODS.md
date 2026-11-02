# Gerenciador de Mods — instalação, análise e confirmação

O Gerenciador MultiMod acompanha imagens locais .bin e .iso de PS1 e gera perfis individuais.

## Abrir no Windows
No diretório do Assistente, execute ABRIR_GERENCIADOR_MODS.bat (incluído no patch v0.3.3).
O Windows precisa ter Python 3.10 ou superior. O scanner não precisa de internet.
Instale Pillow somente se quiser exportar artes pelo scanner de linha de comando.

## Fluxo de uso
1. Clique em **Escolher pasta** e selecione sua coleção de ISOs/BIN.
2. O monitor detecta arquivos novos e inicia a análise quando sua cópia termina. Também é possível usar **Analisar ISO/BIN**.
3. Selecione o resultado para revisar dados **verificados** e **pendentes**. A ausência de dados nunca é preenchida a partir de outro mod.
4. Cada perfil é isolado pela assinatura SHA-256 do disco.
5. Clique em **Ativar perfil selecionado** e confirme. O registro fica em %LOCALAPPDATA%\ForbiddenMemoriesMultiMod\perfil_ativo.json.

## Limitações
- Não altera a ROM, não faz download de jogos e não transfere arquivos pela internet.
- Um mod desconhecido não é reconhecido como X15 por semelhança. Ranks só são rotulados para o hash X15 conhecido.
- Cartas, oponentes, decks e grupos brutos de drops dependem de reconhecimento e validação das estruturas.
- **Fusões ainda não são extraídas automaticamente em mods novos**: o status permanece pendente.
- A ativação do perfil grava a seleção. A integração completa com a interface atual do overlay ainda depende da publicação do código principal do aplicativo. O arquivo integracao_overlay.py é a ponte de leitura pronta para conexão.
- O emulador ePSXe não é inspecionado para descobrir automaticamente a ISO carregada; é necessário selecionar o disco.
- Não há IA generativa nem serviço de nuvem nesta versão; a análise é feita por parsers, validação e assinaturas.
- Não envie ISOs, memory cards, saves ou artes de jogos ao repositório público.

## Falhas de ferramenta na conversa
O erro ClientError ocorreu até quando o ambiente de processamento tentou executar comandos triviais. Isso aponta para uma falha de execução da ferramenta, não para corrupção comprovada das ISOs.
