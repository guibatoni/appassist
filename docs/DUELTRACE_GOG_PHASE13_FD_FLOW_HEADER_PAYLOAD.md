# DUELTRACE etapa 13 — fluxos FD e cabeçalho PS-X EXE

## Evidência real, GOG MOD 2.2, revisão 26
O relatório recebido aponta 722 cartas extraídas, 39 ponteiros candidatos distintos e nenhum adversário publicado. Na melhor janela, 22 registros contêm FD seguido de dois bytes de argumento; os 22 alvos ficam no banco de texto, agrupados em 9 destinos, e contêm FF nas proximidades. Isso não comprova final válido da string. A análise MIPS encontra a assinatura PS-X EXE, mas rejeita o tamanho declarado do payload.

## Mudanças, parser revisão 27
- Sonda `dueltrace_fd_flow_probe.py` percorre rotas de texto com teto de 192 passos, 4 redirecionamentos, limites de banco e detecção de ciclos.
- Comandos F8 não interpretados interrompem o percurso; nenhum nome/ID é publicado por adivinhação.
- `fdFlowWindows` apresenta FF realmente alcançado, glifos após salto, ciclos, controles desconhecidos, limites e profundidade.
- A sonda MIPS registra payload declarado e disponível, sobrecarga, alinhamento e coerência com RAM/entrada, mantendo rejeição de cabeçalhos incompatíveis.
- `Copiar diagnóstico técnico` usa schema 5 com somente contadores e estados de validação.
- A revisão do parser 27 força nova análise da mesma ISO. Cartas, fusões, drops e RANK permanecem preservados.

## Validação pendente
Os testes automatizados usam executáveis sintéticos e não comprovam a recuperação dos adversários no GOG. Depois da Preview Windows aprovada, clicar Atualizar dados e Copiar diagnóstico técnico. Compartilhar os valores de `fdFlowWindows[0]` e `alternativeLayoutSearch.mipsStaticReferences.headerEvidence`.

Referências: motor original em https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled e estrutura PS-X EXE em https://psx-spx.consoledev.net/.

Não mesclar automaticamente na main, nem promover IDs sem prova no emulador.
