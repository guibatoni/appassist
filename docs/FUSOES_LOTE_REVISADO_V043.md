# MultiMod v0.4.3 — Aprovação em lote de fusões revisadas

## Contexto confirmado
Na Biblioteca do **FM Original (Drop x15)**, a análise da v0.4.2 encontrou **2.531 receitas candidatas**, **sete bancos coincidentes** e nenhuma divergência reportada na interface. O usuário posteriormente afirmou que revisou as candidatas e não encontrou erros. Isso é uma **revisão do usuário**, não evidência de que todas foram executadas individualmente no ePSXe.

## Mudanças
- Nova ação **Exportar lista completa CSV**: exporta todos os pares, resultados, nomes, IDs e SHA do mod, não apenas as 750 linhas visíveis por vez.
- Nova ação **Aprovar lote revisado** na aba Candidatas (fusões).
- Confirmação dupla: aviso detalhado e digitação literal `CATALOGO REVISADO`.
- Bloqueio de importação em lote quando a ISO foi alterada desde a importação, o relatório pertence a outro SHA, um dos 7 bancos falha, há divergências/conflitos, as receitas mudaram ou o SHA-256 da lista não corresponde aos sete bancos.
- Cópia de backup do `profile.json` local com nome `profile.json.bak.before_fusion_batch`.
- Dados aprovados incorporados **somente** no perfil daquela ISO, com marca explícita `revisadas_usuario_lote`, não `verificado_no_jogo`.
- Permite que o overlay use o catálogo revisado para sugerir rotas de fusões com as cartas detectadas na mão.
- Receitas anteriormente observadas diretamente no jogo mantêm a evidência superior. Novas confirmações individuais continuam possíveis após o lote.
- O painel e as abas técnicas são notificados imediatamente quando o perfil ativo recebe a aprovação.

## Como usar
1. Fechar Assistente e Biblioteca; atualizar no Launcher para v0.4.3.
2. Abrir o Assistente e a Biblioteca com **Ctrl+Shift+M**.
3. Selecionar **FM Original (Drop x15)**, conferir o SHA e abrir **Candidatas (fusões)**.
4. Exportar o CSV completo (a visualização mostra somente 750 linhas inicialmente). Conferir especialmente as demais linhas.
5. Se a revisão de TODO o conjunto estiver satisfatória, clicar em **Aprovar lote revisado**.
6. Ler o aviso de que não se trata de validação individual no jogo e confirmar digitando `CATALOGO REVISADO`.
7. Confirmar que a coluna Fusões mudou para **revisadas pelo usuário** e que o overlay, usando o perfil correto, sugere rotas.
8. Se aparecer erro de assinatura ou bancos, refazer **Buscar fusões na ISO** e investigar sem aprovar.
9. Testar algumas receitas em duelos reais; confirmar individualmente aquelas observadas.
10. Para outra ISO (FM 13/X15), repetir separadamente. **A aprovação da FM Original não vale para outros mods.**

## Segurança e limitações
- Não inclui ROM, arte, saves ou Memory Cards no patch.
- Não modifica dados do jogo ou do emulador.
- O Assistente ainda não comprova automaticamente qual ISO está realmente aberta no ePSXe; é obrigação do usuário escolher corretamente.
- Sete cópias espelhadas confirmam consistência estrutural, não veracidade em gameplay.
- Aprovação em lote é escolha explícita do usuário e não acontece automaticamente ao instalar.
- Os testes de CI são sintéticos. A compatibilidade real do overlay com milhares de receitas ainda precisa ser verificada no Windows.
- Se uma ISO for reimportada do zero em modo de reextração, as anotações locais de fusão poderão precisar ser recuperadas do backup; não substituir o backup manualmente sem comparar o SHA.
