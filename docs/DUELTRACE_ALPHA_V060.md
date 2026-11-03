# DUELTRACE — Alpha Windows 0.6.0

## Objetivo desta entrega

O produto público oferece apenas **Início**, **Biblioteca de Mods**,
**Biblioteca de Cartas** e **Fusões**. Os painéis anteriores de overlay,
diagnóstico e configurações permanecem no código como modo desenvolvedor
(`DUELTRACE_DEV_MODE=1` ou `--developer`), não são apresentados como
funcionalidades prontas para clientes.

## Como instalar (sem terminal CMD)

1. Acesse a release v0.6.0.
2. Baixe **DUELTRACE-Windows-Alpha.zip**.
3. Extraia toda a pasta `DUELTRACE/` para um local do Windows com permissão de leitura.
4. Abra **DUELTRACE.exe**. O executável PyInstaller usa `--noconsole`.
5. Em **Biblioteca de Mods**, selecione uma ISO/BIN que você possua legitimamente.
6. Marque a extração local de artes e a investigação opcional Ollama.
7. Após a leitura, confira o nível do perfil, a biblioteca e as receitas disponíveis.

Este pacote é um diretório Windows com executável e bibliotecas. Ele **não é
um instalador assinado**, nem um produto comercial final. Não é necessário
abrir PowerShell ou CMD para usar o aplicativo.

## Instalação existente do Launcher MultiMod 0.3

O pacote `patch.zip` da mesma release segue compatível com o atualizador
anterior. A migração do ponto de entrada `assistente_x15.py` continua
reversível e preserva a interface clássica. **Para usar sem terminal**,
prefira o executável `DUELTRACE.exe` da versão Alpha.

## Mecanismo de reconhecimento e Ollama

O reconhecimento automático não é uma IA que compreende qualquer formato
binário arbitrário. O scanner determinístico faz, conforme a compatibilidade
da ISO:

- Identificação por hash SHA-256 e estrutura ISO9660.
- Extração local de nomes, atributos, categorias e oponentes.
- Leitura de tabelas de drops com critérios de soma/estrutura.
- Identificação de efeitos apenas por fonte estrutural/manifesto com origem.
- Extração opcional de imagens com Pillow onde há layout conhecido.
- Investigação de bancos de fusão como candidatos — **não são ativados sem validação**.

O novo `dueltrace_intelligence.py` chama o investigador existente, lê o
inventário dos arquivos **já indexados** e consulta a API local do Ollama
(`127.0.0.1:11434`) após a análise, quando disponível. Apenas resumo JSON
limitado é enviado; não encaminha ISO, Memory Card, saves, ROM ou imagens
para qualquer servidor. **Não requer Ollama** para a análise estrutural.

Ollama é uma *segunda opinião*. Suas sugestões são hipóteses, arquivadas
em `%LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\investigacoes`,
e nunca confirmam drop, fusão, rank, efeito ou probabilidades por conta própria.
Na ausência de Ollama/modelo, o scanner continua normalmente.

Modelo padrão: `qwen2.5:3b`. Instalação do modelo no terminal, opcional:
`ollama pull qwen2.5:3b`. Os modelos são grandes e não acompanham o aplicativo.
Dados e imagens extraídos de ISOs ficam somente na máquina do usuário.

## Organização da pasta e desempenho

- `DUELTRACE/`: aplicativo Alpha e dependências; nenhum ROM distribuído.
- `%LOCALAPPDATA%\\ForbiddenMemoriesMultiMod\\profiles`: perfis do usuário.
- `...\\analises`: extração local e artes.
- `...\\investigacoes`: evidências e hipóteses em cache por SHA.
- `...\\logs`: diagnóstico de inicialização.
- `...\\registro_mods.json`: catálogo de mods (dados do usuário).

Evita-se alterar os endereços de módulos legados na etapa Alpha. A refatoração
para pacote Python estruturado é futura e depende de regressão completa.

## Pendências antes de vender

- Validar com ISOs legalmente obtidas de vários mods e suas estruturas reais.
- Adicionar e testar decodificadores específicos de efeitos e formatos diferentes.
- Revisar direitos autorais, licenciamento de imagens, ícones e distribuição.
- Refinar layout, responsividade, acessibilidade e animações em Windows/DPI.
- Implementar gestão de licenças segura (não colocar chaves no repositório);
  políticas de privacidade, termos, assinatura e atualização segura do executável.
- Rodar testes funcionais end-to-end em PCs de usuários reais.

**Alpha de desenvolvimento, não versão comercial concluída.**
