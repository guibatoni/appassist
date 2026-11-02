# MultiMod v0.4.5 — Monitor temporal e preparação do campo de duelo

## Implementado
- Biblioteca > **Monitor temporal**: iniciar, marcar ação, parar/exportar.
- Amostragem via Tk.after, **somente leitura**, com intervalo configurável de **200/250/500/1000 ms** e limite de **15 a 90 segundos** (até 452 amostras).
- Mesmas regiões da v0.4.4: mão 0xBFF484 (140 bytes) e regiões A/B/C (32 bytes cada).
- Registra timestamp UTC, elapsed_ms, PID, SHA da ISO selecionada, bytes lidos, mão validada, diferenças entre amostras e marcações (fusao, invocacao, ataque, cancelamento, controle).
- Exporta `JSON` completo e `CSV` resumido em `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\diagnosticos_temporais\<SHA>\`.
- O clique de marcador indica o **instante aproximado em que o usuário voltou à janela**, não o instante exato do evento dentro do ePSXe.
- Interrompe com exportação parcial se PID for alterado/erro de leitura; fecha sessão ao fechar Biblioteca.
- Não toca em ISOs, saves, Memory Cards, catálogo de fusões ou RAM (exceto leituras).

## Como testar uma fusão
1. Com a ISO confirmada no overlay pelo usuário, abra a Biblioteca (`Ctrl+Shift+M`) e selecione a ISO ativa.
2. Abra **Monitor temporal**; escolha 250 ms e 45 s.
3. Em duelo com mão válida, clique em **Iniciar gravação**.
4. No ePSXe, realize **UMA fusão**; volte à Biblioteca, clique **Marcar Fusão** e **Parar e exportar JSON/CSV**.
5. Envie apenas o arquivo `.json` resultante. O marcador é uma anotação manual.
6. Faça, em sessão separada, controle de **invocação sem fusão** para comparação.

## Campo de duelo
- Nova aba **Campo de duelo** explica o plano de mapeamento.
- **Não temos endereço de RAM validado da mesa**. Não alegar que a v0.4.5 detecta cartas em campo.
- `scanner/field_fusion_engine.py` implementa motor separado de sugestões teóricas `mão + campo` **somente** mediante entrada externa verificada por RAM com perfil SHA coincidente, lado do jogador, zona de monstro, slots únicos 0–4, IDs 1–722 e receitas já aprovadas no perfil.
- Sem evidência validada, retorna `ready=False`, `suggestions=[]`. A UI não liga esse motor a endereços hipotéticos.
- Nenhuma sugestão de campo é comprovada em gameplay apenas por constar na tabela de fusões.

## Plano de validação da RAM da mesa (futuras versões)
1. Coletar sessões temporais separadas: mesa vazia, invocação de um monstro conhecido, troca de posição, remoção do monstro, duas cartas em slots diferentes, lado oponente (controle).
2. Comparar arquivos e procurar mudanças consistentes **em regiões adequadas**; a v0.4.5 **não varre a RAM para achar a mesa**. As quatro regiões atuais só oferecem ponto inicial de diagnóstico; podem ser insuficientes.
3. Confirmar endereço/offset, estrutura, IDs, lado do jogador, slot e fase do duelo em diversos jogos, mods e sessões/reinicializações do ePSXe.
4. Só então criar leitor da mesa de usuário; em caso de dúvida, mostrar `Campo desconhecido`, nunca cartas inventadas.
5. Cruzar `IDs mão + IDs campo` com receitas aprovadas da ISO, ordenar sugestões e distinguir hipóteses de fusões confirmadas.

## Limites e precauções
- Um sinal `06 0F 80` em região C não identifica fusão: ocorreu também na invocação normal.
- A região B mudou em fusão e em ataque; nenhum dos dois sinais é exclusivo.
- Amostras periódicas podem perder eventos rápidos; intervalos e marcadores não provam automaticamente uma fusão.
- A seleção da ISO é manual; não garante que a mesma ISO esteja em execução no emulador.
- Testes automatizados usam RAM simulada. Teste prático no Windows/ePSXe fica pendente até o usuário instalar.
