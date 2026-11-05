# DUELTRACE — Etapa 5: fronteiras físicas e terminadores alternativos (GOG 2.2)

## Ponto de partida (captura de 05/11/2026)

- ISO: `GOG MOD 2.2 - Drop 15 (NDC).iso`.
- O aplicativo exibe **722 cartas** extraídas estruturalmente do executável.
- Detecta **até 39 nomes candidatos** de adversários, mas ainda não publica o catálogo.
- Mensagem observada: `Há nomes legíveis, mas o terminador padrão 0xFF não foi comprovado. É necessária análise da fronteira física dos registros.`
- Não há confirmação dos IDs dos adversários em duelo real. Fusões e drops do próprio GOG permanecem indisponíveis.

## Mudança técnica (parser revisão 20)

O módulo `scanner/dueltrace_opponent_boundary_probe.py` compara
**39 sequências de ponteiros dentro do mesmo executável**. A rotina não aceita
um novo terminador só porque um byte inválido apareceu muitas vezes.

Só pode selecionar uma tabela estrutural se TODAS as condições ocorrerem:

1. **39 ponteiros distintos, válidos e em ordem física estritamente crescente**.
2. Nomes legíveis do próprio jogo, com identidade por sequência contínua de índices.
3. O primeiro byte não reconhecido em cada registro é **um controle entre 0xF0 e 0xFE**.
4. Os **39 registros usam exatamente o mesmo marcador**.
5. Existem **38 fronteiras físicas consecutivas** entre início de um registro e do próximo, cada uma dentro do orçamento de leitura.
6. Depois do marcador não existem caracteres ou dados não nulos até o próximo registro (preenchimento nulo limitado a 16 bytes).
7. A última string, que pode não ter próximo ponteiro, precisa apresentar pelo menos 8 bytes nulos após o marcador.
8. Há **pelo menos 37 nomes distintos** e apenas **uma sequência completa** elegível. Se também existir outra tabela completa com `0xFF`, a saída é ambígua.

Se a estrutura for única e coerente, os 39 nomes poderão ser extraídos na Biblioteca, mas marcados
**`extraidos_estruturalmente`**. Isso não valida sua numeração no emulador, nem identifica drops ou RANK. Candidatos rejeitados permanecem no JSON local de quarentena.

## Proteções

- Nenhuma escrita na ISO, no executável do jogo ou no Memory Card.
- Nenhuma informação de outro mod é reutilizada por coincidência de ID.
- O perfil continua limitado. Matrizes de drops, rótulos POW/TEC e cálculo do RANK nunca são liberados apenas pela estrutura dos nomes.
- Nomes candidatos e bytes extraídos não são publicados na UI nem nas saídas compactas.
- A revisão 20 força reanálise no botão **Atualizar dados**.
- A validação do parser é sintética; não foi possível abrir a ISO GOG real neste ambiente.

## Como verificar no GOG real

1. Instalar a Preview da revisão 20 somente **após CI e release confirmadas**.
2. Clicar em **Atualizar dados** na Biblioteca de Mods.
3. Conferir se aparecem 39 adversários com aviso de origem estrutural. Caso permaneça sem adversários, o motivo deve continuar visível.
4. Na pasta `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\analises`, abrir o `relatorio.json` correspondente à ISO.
5. Conferir `independent_opponent_discovery.boundaryTerminatorEvidence`, `reasonCode`, `reason` e `candidates`.
6. Se necessário, fornecer também `oponentes_candidatos_nao_verificados.json`, revendo nomes e caminhos particulares. Não enviar ROM, executáveis proprietários ou saves.

## Próximo passo depois de comprovar adversários

Validar a ordem dos 39 IDs contra oponente/duelo observado no ePSXe. Só então cruzar referências MIPS com a estrutura de 117 matrizes para recuperar drops; os três grupos físicos ainda precisarão de associação demonstrável com os rótulos do mod. A etapa de fusões exige leitura própria com testes de receitas em jogo. A automação final deve deixar a importação simples para quem joga.
