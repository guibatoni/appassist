# DUELTRACE — MultiMod Companion · Alpha Windows v0.6.0

DUELTRACE é um assistente independente para **Yu-Gi-Oh! Forbidden Memories (PS1)** e mods. Projeto de fãs, não afiliado aos detentores do jogo. Não contém nem distribui ISOs, saves ou recursos protegidos do jogo.

## Versão Alpha 0.6.0 — experiência de usuário simplificada

A interface pública apresenta quatro seções: **Início**, **Biblioteca de Mods**, **Biblioteca de Cartas** e **Fusões**. O modo desenvolvedor com as ferramentas legadas permanece disponível com `DUELTRACE_DEV_MODE=1` (instalação Python) ou `--developer`.

Existe um pacote **DUELTRACE-Windows-Alpha.zip** com `DUELTRACE.exe` compilado sem console CMD. O patch `patch.zip` continua disponível para o launcher antigo.
A análise local aproveita os parsers, opcionalmente extrai imagens quando reconhecidas, cria um relatório de evidências e consulta **Ollama local** quando disponível, sempre como hipótese — sem aprovação automática.

Veja [escopo e instalação da Alpha](docs/DUELTRACE_ALPHA_V060.md) e [documentação da plataforma 0.5.0](docs/DUELTRACE_PLATAFORMA_V050.md).

## Histórico da plataforma 0.5.0

O novo launcher DUELTRACE Desktop já possui:
- Design system escuro/ciano/dourado, navegação lateral com transições e botões com hover animado.
- Ícone original em formatos SVG, PNG e ICO, gerado a partir de geometria própria.
- Biblioteca de Mods com seleção de ISO/BIN, escaneamento de pasta em segundo plano e reutilização do cache local.
- Biblioteca de Cartas com busca e cinco categorias de cartões (Monstros, Mágicas, Rituais, Armadilhas, Equipamentos).
- Leitura opcional de **textos declarados de efeito** presentes em metadados estruturados na ISO ou manifesto local vinculados ao SHA-256.
- Seções iniciais de Fusões, Overlay, Diagnóstico e Configurações.
- Ferramentas técnicas antigas preservadas no botão **Abrir ferramentas avançadas**.

**Não existe garantia de reconhecimento universal de mods.** O leitor funciona com estruturas que consegue verificar; arquivos incompatíveis ficam sob análise. Textos de efeitos não provam que o mecanismo de jogo os executa. Não inventamos fusões, drops, atributos ou chances.

## Como iniciar

**Windows sem terminal:** extraia `DUELTRACE-Windows-Alpha.zip` e abra `DUELTRACE/DUELTRACE.exe`. Para a instalação antiga, atualize pelo launcher e abra `ABRIR_BIBLIOTECA_MODS.bat` na pasta `app/`. O ponto de entrada Python `tools/abrir_biblioteca.py` continua disponível.

1. Escolha uma ISO/BIN local ou uma pasta com imagens.
2. Aguarde o scanner local e veja os resultados e eventuais alertas.
3. Selecione o perfil e, se estiver parcialmente identificado, revise/autorize somente os recursos conhecidos.
4. Ative o perfil para o overlay. Isso não inicia automaticamente o emulador.

A análise de uma pasta já escolhida pode ser reativada ao abrir o aplicativo. A opção é configurável.

## Documentação

- [Plataforma, design system e novos recursos](docs/DUELTRACE_PLATAFORMA_V050.md)
- [Investigação de RAM — fase anterior](docs/DOIS_CANDIDATOS_V0412.md)
- [Publicação de patch](docs/PUBLICAR_RELEASE.md)

## Segurança e privacidade

O scanner lê ISOs fornecidas localmente em modo somente leitura. Ele não copia, altera nem distribui ROMs, memory cards ou saves. Não envia conteúdo da ISO à Internet. A integração opcional com Ollama trabalha apenas com relatórios compactos; suas sugestões não aprovam dados automaticamente.

A identificação física das cartas na mesa ainda não foi validada; fusões envolvendo a mesa continuam desativadas. A seleção do perfil **não comprova** qual ISO está aberta no ePSXe.

## Desenvolvimento

Requer Python 3.10+; a interface usa Tkinter da biblioteca padrão.

```bash
python -m compileall -q scanner tests
python -m unittest discover -s tests -v
python scanner/abrir_biblioteca.py
```

Repositório: https://github.com/guibatoni/appassist
