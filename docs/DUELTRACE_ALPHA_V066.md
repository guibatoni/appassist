# DUELTRACE Alpha v0.6.6 — Correção gráfica e controle de qualidade

A Alpha 0.6.5 implementou as cadeias de fusão consecutivas de 3–5 cartas e aprimorou a leitura da mão. Durante a geração da captura automática do aplicativo, o GitHub Actions registrou um callback do Tkinter com erro: `NameError: blend is not defined`, dentro do cabeçalho. O processo de captura continuou porque o Tkinter encaminha exceções de callbacks ao relatório de erro, sem necessariamente encerrar o aplicativo.

## Correções aplicadas
- Importado `blend` para o cabeçalho do DUELTRACE.
- O teste estático de referências globais também percorre funções aninhadas, inclusive callbacks de eventos visuais.
- A geração de screenshots Windows registra qualquer exceção de callback e **interrompe o workflow** se alguma ocorrer. Uma imagem capturada não pode mais ser interpretada como evidência de interface funcional caso um callback falhe.
- O teste de janela percorre abas, verifica eventos e detecta erros recebidos pelo Tkinter.

## Preservado da 0.6.5
- Leitura RAM ePSXe somente leitura com duas amostras iguais e PID preferencial explícito.
- Fusões diretas e cadeias de 3–5 cartas na aba Início, sem reutilizar slots.
- Ranking por ATK, indicação de origem e sequência correta.
- Limite de estados com aviso de busca parcial.
- Executável Windows sem CMD e patch para o Launcher antigo.

## Critérios de aceitação
Compilação de sintaxe, testes de regressão e montagem do pacote Windows devem passar. A rotina de captura deve executar sem exceções nos callbacks da GUI. O teste de leitura com a sua ISO e ePSXe real ainda é indispensável.

Esta versão corrige a falha identificada no CI da 0.6.5; prefira a versão 0.6.6 para experimentar o planejador.
