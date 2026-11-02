# Biblioteca de Mods + Investigação Inteligente (v0.3.4)

## O que foi implementado
- Monitoramento de pasta selecionada, detectando novos arquivos .iso e .bin estáveis.
- Scanner estrutural em segundo plano, com hashes SHA-256 e perfis por assinatura.
- Revisão com abas **Validação, Cartas, Oponentes, Drops e Fusões**.
- Inspeção complementar do executável e candidatos de tabelas de fusões u16, marcados **HIPÓTESE NÃO VALIDADA**.
- Ativação **somente após confirmação do usuário** de que a ISO selecionada corresponde à aberta no ePSXe.
- Entrada para Biblioteca **dentro do overlay** por botão/atalho Ctrl+Shift+M, via instalador de integração com backup.
- Banco local de perfis em `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\`. Nada é enviado a serviços de IA.

## Como instalar depois da Release v0.3.4
1. No launcher configurado para `guibatoni/appassist`, clique em **Verificar versão** e **Atualizar pelo GitHub**.
2. **Feche o Assistente antes da integração inicial**.
3. Na pasta `app` instalada, execute `INTEGRAR_BIBLIOTECA_MODS.bat` UMA VEZ.
4. Abra o Assistente. Encontre o botão **Biblioteca de Mods** (no canto inferior do overlay) ou use **Ctrl+Shift+M**.
5. A versão também traz `ABRIR_BIBLIOTECA_MODS.bat` para testar a Biblioteca sem abrir o emulador.
6. Selecione uma pasta de ISOs ou **Importar ISO/BIN**. Abra a aba **Validação** e examine as informações; clique em **Ativar perfil no overlay** somente após conferir o mod aberto no ePSXe.

## Limitações importantes
- A versão **não contém ChatGPT/Gemini executando localmente**: a investigação consiste em parsers, heurísticas e verificações concretas.
- Para mods inéditos, **fusões e regras de ranks permanecem indisponíveis** até validação técnica. Candidatas de fusões NÃO são usadas pelo Assistente.
- O botão no overlay depende da estrutura legada `App.__init__` + `self.compact=CompactPanel(...)`. Se essa estrutura mudou, o instalador **cancela** sem alterar o app.
- O encaixe no overlay atualiza objetos de dados conhecidos, mas o Assistente legado pode exigir reinício para **recalcular todas as visualizações**. Especialmente o painel de rank e outras abas legadas precisam de adaptação posterior para recarga totalmente dinâmica.
- A Biblioteca **não determina automaticamente a ISO ativa no ePSXe**. A identificação feita ao selecionar o arquivo depende da confirmação do usuário.
- Escaneamento e exportação das duas ISOs citadas na conversa ainda precisam de execução local e validação por logs. Não afirmar extração concluída.
- ISOs, saves, Memory Cards e artes extraídas **não entram no patch** nem no GitHub.
- O recurso de fusão não herda receitas de outro mod, mesmo quando os IDs coincidem.

## Reversão da integração
O instalador guarda um backup `assistente_x15.py.bak.library.YYYYMMDD-HHMMSS` na mesma pasta. Feche o app, copie o backup para `assistente_x15.py` e inicie novamente.

## Próximas versões
- Atualização completa de UI/cards/strategy/rank durante uma sessão, sem reiniciar overlay.
- Leitura da ISO ativa dentro do processo ePSXe, com comparação de hashes/assinaturas.
- Extratores específicos de fusão e rank por famílias de mods, com testes cruzados.
- Plugin opcional de IA assistida com consentimento, apenas metadados e trechos autorizados, jamais uma ROM inteira.
- Autotestes de amostras dos dois mods enviados.
