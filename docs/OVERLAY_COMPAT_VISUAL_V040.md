# MultiMod v0.4.0 — correção de nomes no overlay legado

## Sintoma confirmado no Windows
A Biblioteca confirma 722 cartas no perfil **FM Original (Drop x15)**, mas a tela `MÃO DETECTADA` continua exibindo `Carta #420 (ID somente)`, `Carta #123 (ID somente)` etc. A indicação `JOGO: Desconhecido` continua separada, pois o ePSXe não forneceu uma identificação comprovada da ROM ativa.

## O que mudou
- `scanner/overlay_card_labels.py`: compatibilidade visual com `tk.Label`, `ttk.Label` e itens de texto em `tk.Canvas`. Atualiza somente rótulos no formato `Carta #123 (ID somente)` para o nome da mesma ID **do perfil aprovado**.
- Mantém nome correto após redesenho periódico do painel antigo.
- Reverte o rótulo para `Carta #123 (ID somente)` se outro mod for selecionado sem essa ID, evitando mistura de nomes.
- Não altera tipo, rank, LP, pontuação ou fusões; esses recursos continuam exigindo validação específica.
- A confirmação de ativação exibe o número de rótulos efetivamente substituídos no momento. Zero não prova falha, pois o painel pode criar a mão depois e o sincronizador tenta novamente.
- Se o painel usar um componente não reconhecido, a correção pode exigir modificar `painel_compacto.py` especificamente. Testes automáticos usam componentes simulados, não a instalação Windows real.

## Atualizar
1. Feche **Biblioteca** e **Assistente**. Não é necessário encerrar o ePSXe.
2. No launcher, verifique a versão e instale `v0.4.0` pelo GitHub.
3. Inicie o Assistente e abra a Biblioteca (`Ctrl+Shift+M`).
4. Escolha a ISO realmente carregada no ePSXe, depois clique em **Ativar perfil no overlay**.
5. Confira se a mão mostra os nomes das IDs (exemplos: 123, 420) e o diagnóstico `Rótulos atualizados no momento` no aviso de ativação.
6. Mesmo mostrando nomes, o assistente **não confirmou automaticamente** que a mesma ROM está no ePSXe.
7. Não precisa reinstalar o hook; `INTEGRAR_BIBLIOTECA_MODS.bat` foi executado com sucesso anteriormente.

## Se os nomes ainda não aparecerem
Forneça os arquivos `app/painel_compacto.py` e `app/assistente_x15.py` (após remover qualquer dado privado). Esses dois arquivos ainda não estão no repositório e são necessários para corrigir a rotina exata de renderização, caso use widgets ou caches específicos.
Não compartilhe saves, Memory Cards, ROMs ou tokens só para investigar um rótulo.
