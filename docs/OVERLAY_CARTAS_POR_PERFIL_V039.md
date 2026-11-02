# MultiMod v0.3.9 — nomes reais das cartas na mão do overlay

## Sintoma
As 722 cartas apareciam corretamente na Biblioteca de Mods, mas a mão detectada no overlay exibia `Carta #123 (ID somente)`.

## Causa provável na integração
A Biblioteca atualizava atributos como `app.cards` e `compact.cards` atribuindo **novos dicionários**. Referências capturadas durante a inicialização pelo CompactPanel, Estrategista ou callbacks antigos podiam continuar apontando ao catálogo anterior/vazio. Também não havia observador ativo do registro `perfil_ativo.json` na ponte de UI.

## Correção
- `overlay_profile_bridge.py` aplica os nomes, ATK/DEF e IDs de cada perfil aprovado, **atualizando os mesmos dicionários e listas in-place**; isso preserva referências de callbacks preexistentes.
- Reconstrói o estrategista quando sua classe está disponível; não inclui fusões de outros mods.
- Remove dados X15 de drops/rank caso o perfil atual não tenha essas regras confirmadas.
- A `biblioteca_mods.py` ativa um observador do perfil persistido, permitindo repropagar mudanças ao overlay.
- Exibe confirmação de quantas cartas o perfil disponibiliza; **escolher uma linha/aba na Biblioteca não equivale a ativá-la**.
- Testes automatizados verificam o ID 123 em um objeto de overlay simulado, além de troca de mod sem nomes antigos persistentes.

## Atualização e teste
1. Feche Biblioteca e Assistente, mantendo o Launcher.
2. No Launcher, `Verificar versão → Atualizar pelo GitHub`, confirmar `0.3.9`.
3. Reabra Assistente e Biblioteca com `Ctrl+Shift+M`. **O hook já instalado importa a ponte atualizada; não executar novamente INTEGRAR_BIBLIOTECA_MODS.bat.**
4. Selecione a ISO realmente carregada no ePSXe; clique **Ativar perfil no overlay** e aceite a confirmação.
5. O quadro `MÃO DETECTADA` deverá exibir nome em vez de `Carta #123 (ID somente)` para IDs presentes nas 722 cartas reconhecidas.
6. A ativação **não identifica automaticamente a ISO carregada no ePSXe**; o usuário deve confirmar o arquivo correto. Rank e fusões desconhecidos continuam desativados.

## Limites da versão
- O patch corrige o encaixe do catálogo no modelo da aplicação, mas foi testado em GitHub Actions com objetos simulados. A exibição efetiva no CompactPanel legado deve ser confirmada em Windows.
- Não modifica `assistente_x15.py` nem `painel_compacto.py` novamente. O hook v0.3.5 deve estar instalado.
- Se os nomes continuarem como IDs mesmo após confirmação, coletar o log do Assistente e os arquivos `assistente_x15.py` e `painel_compacto.py` da instalação atual para revisar a rotina real de renderização, preservando seus dados pessoais.
- A coluna `JOGO: Desconhecido` pode continuar a descrever **identificação da ISO ativa no emulador**, que é diferente do perfil manual aprovado na Biblioteca.
