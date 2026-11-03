# DUELTRACE — Início da plataforma 0.5.0

Esta entrega inicia as frentes de arquitetura MultiMod, catálogo, automação e redesign visual. **Não é a versão final 1.0 nem declara compatibilidade universal com mods.**

## 1. Direção visual

As artes conceituais aprovadas neste projeto são a referência para uma identidade **egípcia, mística e tecnológica**: fundos azul-marinho/pretos, contornos ciano, destaques dourados e estados verdes/amarelos de validação.

Implementações reais:
- `scanner/dueltrace_theme.py`: tokens de cor, estilo de tabelas, botões com hover animado (aproximadamente 150 ms) e componentes.
- `scanner/dueltrace_desktop.py`: launcher com navegação entre sete páginas, transição lateral e indicadores alimentados por dados reais.
- `scanner/dueltrace_brand.py`: gera ícones PNG e ICO para Windows, sem pacote adicional.
- `assets/dueltrace-mark.svg`: logomarca vetorial compacta.

As artes originais são mockups, não telas executáveis. Elementos não implementados nelas (percentuais de IA, cartas ilustrativas, estatísticas e LP fictícios) **não aparecem como dados reais** no novo launcher.

O launcher anterior permanece acessível por **Abrir ferramentas avançadas**, preservando os diagnósticos RAM e demais operações legadas.

## 2. Biblioteca de Mods e fluxo automático

`scanner/mod_autopilot.py` recebe uma ISO/BIN local ou pasta, descobre arquivos com extensões permitidas e aciona o extrator atual em segundo plano. Reutiliza o cache de `ModCatalog`, mostra progresso, preserva o SHA-256 e apresenta:
- Mod conhecido e validado (estritamente conforme os critérios do perfil).
- Mod parcialmente reconhecido e que necessita revisão.
- Estrutura não identificada, sem liberação indevida dos dados de outro mod.

A opção **Ao iniciar, analisar automaticamente a pasta salva** é configurável. A aplicação não envia ROMs pela rede, não executa emuladores automaticamente e não altera arquivos de jogo. Mods parciais exigem confirmação antes de ativar; estruturas desconhecidas não recebem catálogo inventado.

A compatibilidade atual é com o **layout reconhecido de Forbidden Memories PS1**, incluindo ISO 2048 e BIN 2352 onde os leitores identificam corretamente os arquivos e tabelas. Mods que alteram formato, endereços, codificações, conteúdo interno ou regras exigem novos adaptadores/testes. O objetivo de reconhecer qualquer mod é **um objetivo de produto, não um recurso já garantido**.

## 3. Biblioteca de Cartas (cinco categorias)

`scanner/card_catalog.py` mapeia os códigos FM padrão na tabela de atributos:
- 0..19: **Monstros** (20 subtipos conhecidos).
- 20: **Mágicas**.
- 21: **Armadilhas**.
- 22: **Rituais**.
- 23: **Equipamentos**.
- Outros ou ilegíveis: **Não identificado**.

Os códigos vêm dos dados extraídos do executável, nunca de suposições pelo nome da carta. Para mods que redefinem esses códigos, o mapeamento padrão precisa de revisão. **Nenhum texto de efeito é inventado.**

Os perfis exibem origem da categoria, tipo e status do efeito, e a nova tela permite buscar por ID, nome ou texto de efeito quando este existir.

## 4. Efeitos fornecidos pelo mod

O aplicativo lê duas fontes ESTRUTURADAS opcionais:

**Dentro da ISO**, via `scanner/mod_effects_iso.py`, de nomes:
- `DTEFFECT.JSON`
- `DUELTRACE/EFFECTS.JSON`
- `DUELTRACE/CARDS.JSON`

Exemplo de documento **embutido na ISO** (sem hash autorreferente):

```json
{
  "schema": 1,
  "effects": [
    {"id": 650, "text": "Texto oficial fornecido pelo autor deste mod."}
  ]
}
```

**Ao lado da ISO**, via arquivo `NOME_DO_MOD.iso.dueltrace-effects.json`, usando o SHA-256 **exato** da ISO:

```json
{
  "schema": 1,
  "rom_sha256": "64 caracteres hexadecimais do SHA-256 real",
  "effects": [
    {"id": 650, "text": "Texto do efeito revisado pelo autor do mod."}
  ]
}
```

Esses exemplos são apenas de formato. Nunca incluem cartas/efeitos não presentes no mod. Os dados são limitados em tamanho, IDs duplicados são rejeitados, o hash externo deve corresponder à imagem, e a informação da origem acompanha a carta. **Uma descrição é uma declaração, não comprovação de que a mecânica foi implementada no motor do jogo.**

Para mods que guardam efeitos em tabelas binárias proprietárias, precisamos desenvolver decodificadores específicos. Não realizar pesquisa de strings às cegas e declarar o resultado como efeito confirmado.

## 5. Integração com o overlay

`scanner/integracao_overlay.py` agora transporta categoria, rótulo de tipo e texto de efeito **apenas** se o perfil ativo autorizar o respectivo recurso e houver origem. O app não afirma reconhecer automaticamente o campo; as fusões mão + campo continuam desativadas.

## 6. Interface e uso

Abra `ABRIR_BIBLIOTECA_MODS.bat` para entrar no novo DUELTRACE Desktop. No novo painel:
1. Escolha **Importar ISO/BIN** ou **Escanear pasta**.
2. O motor extrai o que conseguir reconhecer e apresenta o estado do perfil.
3. Confira o resultado na **Biblioteca de Mods** e a distribuição real na **Biblioteca de Cartas**.
4. Clique **Ativar perfil**. Um mod parcial pede confirmação única; não libera recursos não identificados.
5. Jogue em seu emulador normalmente; a seleção do perfil não confirma qual ISO o ePSXe abriu.

Para tarefas de pesquisa e retrocompatibilidade: **Abrir ferramentas avançadas**.

A janela contém navegação com transições e botões animados, mas a nova arte da marca ainda é uma versão vetorial inicial. O acabamento visual completo dos mockups, animações GPU, cartas artísticas e sobreposições mais elaboradas exige trabalho gráfico adicional e testes em Windows.

## 7. Próximas frentes técnicas

- Identificação de layouts de FM13, X15 e demais mods por **evidência e testes separados**, sem assumir que o layout do X15 seja universal.
- Decodificadores de textos de efeito proprietários, sem inventar regras.
- Regras específicas por mod para mágicas, rituais, armadilhas e equipamentos.
- Integração completa das artes do usuário (com procedência e autorização), transições e responsividade da interface.
- Fluxo de execução do emulador e overlay vinculados ao perfil ativo, com confirmação segura.
- Empacotamento nativo do Windows e revisão de desempenho, acessibilidade, DPI e segurança.
- A leitura de cartas no campo permanece fora do escopo até validação independente.

## 8. Qualidade e segurança

`python -m compileall -q scanner tests`

`python -m unittest discover -s tests -v`

Todas as alterações de produto fazem parte de um patch com verificação SHA-256 de artefatos no pipeline do GitHub Actions. Sem ROMs comerciais, memory cards, saves ou artes extraídas distribuídas.
