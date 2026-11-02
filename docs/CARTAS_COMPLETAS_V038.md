# Biblioteca de Mods — Listagem completa de cartas (v0.3.8)

## Problema corrigido
A interface `preview_model()` exibia apenas os **primeiros 180 registros**, embora a importação tivesse extraído os 722 cards da ROM de Forbidden Memories.

## Ajustes
- A aba **Cartas** agora lê todos os registros validados no perfil local (722 se o perfil os tiver).
- **Buscar ID ou nome** permite encontrar qualquer carta. Busca numérica encontra o ID exato e busca textual encontra trechos do nome, sem depender do idioma.
- Contador visível mostra **N de 722 cartas** ao digitar ou limpar o filtro.
- As tabelas de drops validadas não são mais truncadas silenciosamente em 180 registros.
- Nenhuma ISO é reprocessada para visualizar o restante dos registros. Dados são carregados do perfil local.
- Perfis parciais continuam com ranks e fusões desconhecidos indisponíveis.

## Atualizar
1. Feche a **Biblioteca** e o **Assistente**, deixando o Launcher aberto.
2. Verifique a versão e clique em **Atualizar pelo GitHub** para instalar v0.3.8.
3. Inicie o Assistente e abra a Biblioteca pelo botão ou **Ctrl+Shift+M**. Não é necessário reexecutar `INTEGRAR_BIBLIOTECA_MODS.bat`.
4. Selecione `FM Original (Drop x15)` e abra **Cartas**.
5. Confira o contador **722 de 722 cartas** se o perfil realmente tiver 722.
6. Pesquise IDs `181`, `492` e `722` para confirmar que a interface lista cards além do 180.
7. Se o contador for inferior a 722, essa limitação está no **perfil extraído**, não na lista: nesse caso, revisar `profile.json` e `relatorio.json` localmente.

## Testes
- Testes sintéticos verificam visibilidade de 722 cartas e 3.972 entradas de drops.
- Busca por ID, nome, casos inexistentes e bloqueio de dados não confirmados.
- Não publica nem modifica ROMs, saves ou Memory Cards.
