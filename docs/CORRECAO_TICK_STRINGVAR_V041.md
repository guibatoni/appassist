# Correção v0.4.1 — Cartas no overlay continuam como "ID somente"

## Origem confirmada nos arquivos Python reais enviados pelo usuário
Em `painel_compacto.py`, a mão usa `tk.StringVar` e Labels com `textvariable=title`. O método `CompactPanel.tick()` só chama `self.hand[n].set(c["name"])` quando ocorre:
```python
if self.last != ids or self.last_pid != rd.pid:
```
Ativar outra ROM na Biblioteca alterava `self.cards`, mas **não invalidava** `self.last` e `self.last_pid`. Com os mesmos 5 IDs e PID, o painel não redesenhava os nomes. A abordagem v0.4.0 tentava configurar o texto dos `Label`, porém eles têm `textvariable` e o valor original podia continuar prevalecendo.

Um segundo fator: `assistente_x15.App.__init__` agenda `initialize_profile` via `root.after(100,...)`, **depois de criar a ponte**, e `apply_profile` pode limpar/substituir `self.cards`, restaurando o catálogo "unknown".

## Correção
- `overlay_profile_bridge.py`: ao aplicar um perfil, invalida `compact.last` e `compact.last_pid`. No próximo `tick` (700 ms), a mão é renderizada pela rotina original, usando os nomes do catálogo selecionado.
- Atualiza `profile_has_cards` e `profile_has_fusions` conforme dados validados, sem inventar fusões/ranks.
- Mostra mensagem de **CATÁLOGO** ativo, diferenciando-a da ISO efetivamente aberta no ePSXe (ainda não verificada).
- `biblioteca_mods.py`: confere periodicamente se um carregamento do perfil legado sobrescreveu os cartões; **só reaplica quando detectar divergência**, evitando recalcular desnecessariamente em cada leitura.
- Testes reproduzem a condição real `last/PID`, a passagem pelos `StringVar` e a mudança de mod com os mesmos IDs.
- Os dois arquivos completos enviados pelo usuário não foram publicados ou substituídos. O patch contém apenas os módulos MultiMod já integrados na pasta `app/tools`.

## Instalação no Windows
1. Feche a Biblioteca e o Assistente, mas pode deixar o ePSXe aberto.
2. No launcher, verifique a versão e atualize para **v0.4.1** pelo repositório `guibatoni/appassist`.
3. Inicie o Assistente; a instalação da Biblioteca já feita anteriormente permanece válida. Não execute novamente `INTEGRAR_BIBLIOTECA_MODS.bat`.
4. Na Biblioteca (`Ctrl+Shift+M`), selecione exatamente o perfil correspondente à ISO aberta no ePSXe e clique em `Ativar perfil no overlay`.
5. Em até um ciclo do painel, os nomes da mão devem aparecer em vez de `Carta #123 (ID somente)`, e ATK/DEF devem vir do mesmo perfil.
6. **Não** conclua que a ISO ativa foi identificada automaticamente; isso continua exigindo verificação independente.

## Próximo diagnóstico se não funcionar
No painel técnico, abrir o Assistente pelo terminal `py -3 assistente_x15.py`, observar se aparece `MultiMod: perfil carregado no overlay` ou mensagens de exceção. Enviar erro e captura, sem expor ROM, Memory Card ou dados pessoais. O overlay real no Windows ainda precisa confirmar a correção, apesar dos testes sintéticos.
