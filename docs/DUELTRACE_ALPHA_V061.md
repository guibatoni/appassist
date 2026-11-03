# DUELTRACE Alpha 0.6.1 — Diagnóstico por ISO/BIN

A Alpha 0.6.0 apresentou 722 cartas para diversos mods, mas a etiqueta de Ollama/artes refletia a última ISO processada, não a linha selecionada. A Alpha 0.6.1 corrige o contexto da interface.

## Verificar um mod

1. Atualize ou extraia a versão Alpha Windows 0.6.1.
2. Vá à **Biblioteca de Mods**, selecione **uma** ISO/BIN na lista.
3. Clique **Ver diagnóstico**.
4. Confira quantidade de cartas, oponentes, entradas de drops, efeitos com origem, fusões disponibilizadas, artes e justificativa de extração.
5. Clique **Copiar diagnóstico** e cole o texto na conversa de suporte. Não inclui caminhos locais completos ou ROM.
6. Se quiser investigar novamente as artes, selecione a ISO/BIN e execute a análise com “Extrair artes locais” marcado.

## Interpretação

- **722 cartas:** tabela de nomes/atributos reconhecida, não significa que todos os dados da ISO foram interpretados.
- **Artes não solicitadas / sem registro:** nenhuma tentativa verificável no relatório.
- **Artes parciais / nenhuma arte extraída:** consulte a justificativa detalhada, que pode indicar tamanho insuficiente do WA_MRG, paleta ou dependência.
- **Efeitos com fonte = 0:** não há texto de efeitos acompanhado de procedência; o mod pode ter efeitos binários ainda não decodificados.
- **Fusões = 0:** não há receitas habilitadas como revisadas/confirmadas. Bancos candidatos ficam no relatório de investigação e não são ativados por Ollama.
- **Ollama em cache:** uma sugestão local já foi produzida para as mesmas evidências. Na 0.6.1, quando as evidências mudam, o cache é invalidado; IA não valida dados por si só.

## Proteções

ISO/BIN nunca é modificada. Resultados permanecem locais. Não há promessa de suporte universal ou de identificação automática do conteúdo binário de todo mod. A validação visual da Alpha e dos resultados de mods reais permanece necessária.
