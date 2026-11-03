# DUELTRACE — MultiMod Companion (Windows)

DUELTRACE é um assistente independente para **Yu-Gi-Oh! Forbidden Memories (PS1)** e mods. Projeto de fãs, não afiliado aos detentores do jogo. Não contém nem distribui ISOs, saves ou recursos protegidos do jogo.

## Versão da plataforma: 0.5.0 — início do redesenho

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

Instale o último patch pelo atualizador (ou use o pacote da Release conforme sua instalação atual), depois abra `ABRIR_BIBLIOTECA_MODS.bat` na pasta `app/`. O ponto de entrada `tools/abrir_biblioteca.py` abre o novo desktop.

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
