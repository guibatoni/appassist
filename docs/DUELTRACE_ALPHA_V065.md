# DUELTRACE Alpha 0.6.5 — Estabilidade da mão e rotas de fusão de 3 a 5 cartas

## Evolução
A interface pública mantém quatro abas. Na **aba Início**, a área de fusões passa a ter dois modos acessíveis por botões:
- **Fusões diretas (2):** pares entre dois slots da mão, igual à versão 0.6.4
- **Cadeias (3–5):** sequências consecutivas em que o resultado de cada fusão se combina com outra carta ainda presente na mão

Os resultados vêm exclusivamente do banco de fusões disponibilizado pelo perfil do mod ativo. Não se consulta um modelo de IA para inventar receitas.

## Como o planejador funciona
O estado da busca contém uma máscara de cinco bits (slots já consumidos) e o ID do monstro resultante. A primeira combinação consome dois slots diferentes; cada etapa posterior consome um slot diferente dos anteriores e usa o resultado da etapa anterior.

- Explora pares iniciais e suas continuações
- Evita reutilizar um slot, inclusive quando existem cartas duplicadas na mão
- Mescla estados equivalentes, dando preferência à proveniência de etapas individualmente observadas no jogo
- Mantém a **ordem de execução dos slots** separada da lista ordenada dos slots consumidos
- Ordena por ATK do resultado, conhecido no catálogo do mod; ATK ausente aparece por último
- Não repete o mesmo ID final com rotas redundantes; recomenda uma sequência por resultado
- Limita a 20.000 estados e indica **busca parcial** se atingir o limite. Busca parcial nunca é apresentada como solução ótima exaustiva
- O usuário pode selecionar a linha e consultar as etapas em ordem

**Critério de confiança:** sete bancos estruturais iguais podem validar uma receita como extraída da ISO, mas não garantem sua execução em todos os duelos. Mesmo quando as etapas individuais foram observadas, a cadeia completa recebe `route_observed_in_game=False`.

## Estabilidade do ePSXe
A leitura continua restrita a 140 bytes no endereço de mão já documentado do ePSXe. Para evitar mostrar uma mão parcialmente alterada no meio da compra/substituição de cartas, agora são exigidas **duas leituras consecutivas idênticas e válidas**.

Quando o DUELTRACE iniciou o emulador e conhece seu PID, não transfere a conexão para outro ePSXe se aquele processo desaparecer. Isso evita mostrar cartas de uma instância errada. As cinco cartas e sugestões são limpas após leitura inválida ou desconexão.

**Limite importante:** o aplicativo ainda não comprova que a ISO que o ePSXe está executando corresponde ao perfil selecionado.

## Distribuição / testes
O pacote Windows continua sendo um diretório com `DUELTRACE.exe` executado sem CMD. A release inclui o patch incremental para a instalação antiga e prévias automatizadas com dados sintéticos, sempre indicadas como `TESTE`.

Testes automatizados incluem duplas, cadeias de 3–5, cartas duplicadas em slots diferentes, limite de busca, transição de leitura RAM, múltiplos PIDs, ordenação, procedência e renderização Tk. Ainda será necessário testar a interação com o ePSXe real e as ISOs do usuário antes de chamar a versão de estável ou comercial.

## Próximas etapas
1. Confirmar no Windows que a leitura da mão é estável ao comprar/jogar cartas e que o perfil do mod coincide com o jogo em execução.
2. Refinar detalhes visuais da área de rotas para a resolução e a escala de DPI do usuário.
3. Investigar resultados com a mesa e validação de efeitos, somente após mapear suas estruturas RAM/ISO com evidências.
4. Implementar instalador, atualização verificada, proteção de dados e licenciamento.
