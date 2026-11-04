# DUELTRACE v0.9.0 — restauração experimental da leitura RANK em outras ISOs

**Origem:** v0.8.9, PR #39, commit `97eff1fb3e91bae54d9d3111bc2037eec18ae178`.  
**Branch:** `feature/dueltrace-v090-restore-legacy-rank-probe`.

## Solicitação

Restaurar a leitura de Spoils/RANK utilizada pelo Assistente antigo em Original, FM13 e demais ISOs; **somente** o Remaster X15 exato terá Z-POW, S-POW e S-TEC. Todo outro SHA utiliza S-POW, A-POW, B-POW, C-POW, D-POW, D-TEC, C-TEC, B-TEC, A-TEC, S-TEC.

## Alterações implementadas

- A ponte deixa de abortar imediatamente quando a ISO tem perfil local válido, mas `rank_points` não foi encontrado. **Tenta** o leitor antigo `read_rank_candidate` no endereço de RAM host `0xB41990`, coletando duas amostras estáveis de 32 bytes do processo ePSXe. Nunca escreve na memória.
- Para ISOs ainda sem binding aprovado, esta sondagem é classificada como **experimental**, nunca como validação universal do endereço. Ela pode falhar em mods que movem a estrutura ou alteram seu formato.
- A primeira leitura plausível solicita **conferência dos LP exibidos no jogo**. Após confirmar os LP, o aplicativo observa os contadores periodicamente (850 ms) e exige **duas transições reais, coerentes e sucessivas** antes de exibir uma projeção experimental.
- Políticas de coerência: contadores não negativos, sem decrementos em contadores de ações, sem saltos superiores a 8 por observação (turnos no máximo 2), sem mudança de LP absurda ou troca de PID/ISO. Leituras paradas não contam como eventos. Mudança de duelo zera a calibração.
- Uma vez observado o mínimo, a calculadora usa os **mesmos dez critérios**, base 50 e bônus hipotético +2 por vitória LP, provenientes da investigação X15. O RANK exibido para ISO não-X15 usa exclusivamente os dez nomes e limites clássicos, classificados por SHA. Isso é uma **estimativa candidata**; a fórmula de outro mod não foi comprovada apenas por ler números plausíveis.
- A projeção experimental é rotulada e não habilita `capture_rank_prediction`, auditorias automáticas ou gravação de `rank_runtime_binding`. A leitura validada X15 e os bindings comprovados permanecem com fluxo existente e sem downgrade de confiança.
- O painel RANK da Central de Duelo permanece compacto: cinco cartas, fusões e RANK ao vivo. Enquanto o leitor experimental aguarda eventos, mostra 0/2, 1/2 e 2/2 mudanças. A condição e a hipótese de leitura são explícitas sem ocupar o catálogo Drops.
- O diagnóstico de ISO informa a disponibilidade do leitor antigo mesmo sem tabela WA. Não é mais necessário encontrar uma tabela RANK apenas para fazer um **teste** de leitura da RAM no endereço legado.

## O que NÃO foi provado

- O endereço `0xB41990` **não é garantido** em todos os mods; leitura de bytes coerentes não valida o vínculo RAM ou a fórmula do SLUS.
- A seleção da ISO no DUELTRACE ainda não garante que o ePSXe abriu a mesma ISO. É necessário comparar o jogo ativo.
- As duas alterações observadas melhoram plausibilidade, mas **não substituem duelos independentes de validação** contra o RANK final mostrado pelo jogo.
- Não existe autodescoberta completa de novos endereços host RAM nesta entrega. Isso exigirá coleta de traces e observações específicas por ISO.
- Marcador X15 de LP/deck-out continua reservado exclusivamente ao SHA Remaster X15.
- RANK de leitura experimental não deve ser comercializado como resultado confirmado.

## Próximo teste real

1. No DUELTRACE selecione a ISO Original ou FM13 e abra a mesma ISO no ePSXe; deixe apenas uma instância de ePSXe ativa.
2. Comece o duelo e observe se o RANK entra em **Confirme seus LP** em vez de **RANK indisponível por tabela ausente**. Se o registro não for plausível, o programa informa a ausência; não inventa score.
3. Confirme os LP reais. Faça duas ações como jogar magia e finalizar turno; verifique o contador **0/2→1/2→2/2** e a projeção experimental de dez classificações.
4. Compare a nota e o RANK final do jogo com a previsão; registrar observações independentes, especialmente as divergências históricas 46/45 e 50 S-TEC.
5. Para mods que não usam o mesmo endereço RAM, registrar traces específicos; não remover proteções nem tratar a ausência de dados como erro da fórmula.

## Prompt de continuidade

> Continuar DUELTRACE v0.9.0. Repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v090-restore-legacy-rank-probe`. A v0.9.0 restaurou uma sondagem de RANK legada para qualquer ISO selecionada com perfil: leitura READ-ONLY de duas amostras em 0xB41990, conferência LP e exigência de duas mudanças coerentes dos contadores, com polling 850 ms. O resultado em ISOs não-X15 é **experimental** e usa apenas dez RANKs originais. Z-POW/S-POW/S-TEC são exclusivos do SHA exato X15. O leitor não finge que a RAM de qualquer mod está validada, não habilita captura de previsões experimentais e não altera bindings aprovados. Verificar PR, commit e CI antes de declarar testes aprovados. Próxima tarefa: validar em ePSXe real (X15, Original, FM13), confirmar a ISO realmente executada e identificar offsets RAM alternativos em mods que ainda não respondem; manter funções da mão, fusões, drops, atualizador verificável e dados locais.
