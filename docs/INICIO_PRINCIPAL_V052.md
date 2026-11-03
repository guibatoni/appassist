# DUELTRACE v0.5.2 — Nova interface como entrada principal

A v0.5.1 instalou o novo DUELTRACE Desktop dentro de `app/tools/`, mas o launcher clássico 0.3 continuou abrindo `app/assistente_x15.py`. A atualização do pacote **não substitui automaticamente o launcher antigo**.

## Ativar a interface nova

1. Instale a release v0.5.2 pelo launcher 0.3.
2. Feche o Assistente Multimod e volte para a pasta `app/`.
3. Execute **`ATIVAR_NOVA_INTERFACE.bat`** UMA VEZ.
4. O instalador valida a estrutura `assistente_x15.py`, verifica os módulos do DUELTRACE, salva backup versionado e injeta uma ponte mínima no início do arquivo.
5. Volte ao launcher 0.3 e clique em **INICIAR ASSISTENTE**. Esse botão agora abre o **DUELTRACE Desktop**.
6. No DUELTRACE, use **Abrir Assistente Clássico** para acessar o overlay legado e os diagnósticos.
7. A própria janela antiga do launcher de atualizações **continua com a aparência de antes**, pois é outro programa fora da pasta de patch.

## Desfazer sem perder dados

Com o assistente fechado, execute `RESTAURAR_INTERFACE_ANTIGA.bat` na pasta `app/`. O programa remove exclusivamente a ponte `DUELTRACE_MAIN_ENTRY_BEGIN/END`, cria novo backup e mantém os hooks legados. Depois disso, o botão do launcher volta a abrir o Assistente original.

## Segurança

O patch não inclui ISOs, saves, Memory Cards ou artes comerciais. A alteração da entrada é **opt-in**: instalar a release não muda automaticamente o modo de inicialização. Não alterar o launcher externo nem sobrescrever o `assistente_x15.py` inteiro. Sem suporte universal a mods nem reconhecimento automático validado do campo.

## Verificação

- Compilação e testes executados no GitHub Actions para Windows.
- Testes automatizados cobrem o fluxo nova interface / modo legado / restauração e falha segura.
- A validação visual e a abertura pelo launcher original ainda precisam de confirmação em uma instalação Windows real.
