# DUELTRACE — Notas da atualização

## Novidades
- **Fusões em duas direções (v57):** toda carta mostra receitas em que é usada como material e receitas que a produzem como resultado final; veja os dois ingredientes, seus ATKs, o resultado e seu ATK, com ordenação e navegação independentes.
- **Atualização sem GitHub Actions (v57):** o desenvolvedor gera, assina, verifica e publica o ZIP completo diretamente no Windows; os clientes baixam as próximas versões anonimamente do canal público de executáveis.
- **Atualizações para todos os clientes:** o DUELTRACE consulta o canal público separado de pacotes Windows, sem exigir conta GitHub, GitHub CLI, token ou acesso ao código-fonte privado. A atualização acontece na mesma pasta por um único botão.
- **Distribuição controlada:** a publicação ao público exige testes locais, assinatura de editor confiável, análise Microsoft Defender e SHA-256 do ZIP antes de disponibilizar o executável.
- **Cartas por clique (v55):** a janela de informações abre somente ao clicar em uma carta na Central de Duelo, Biblioteca, Fusões ou Drops; passar o mouse não abre pop-ups.
- **Informações completas:** a janela mantém arte, descrições maiores, efeitos, locais de drop e possíveis fusões com ATK do resultado; feche por X, Esc ou clicando fora.
- **Interface adaptável:** o DUELTRACE reorganiza navegação, cartas, fusões, drops e detalhes em telas 9:16, 16:9, 16:10, 4:3 e ultrawide, sem distorcer as cartas.
- **ePSXe:** busca dinâmica de RAM quando o endereço antigo não funciona, com suporte a executáveis identificados por número de versão (somente Windows).
- As versões Windows verificadas serão disponibilizadas em um repositório próprio de releases, separado do código privado.
- Aba Fusões: escolha pesquisar por **resultado final**, **material da fusão** ou **ambos**, por nome ou ID da carta.
- Patch notes exibidos em uma janela dentro do aplicativo, sem abrir o navegador.

## Melhorias
- Atualizador mostra os números reais dos builds Preview instalados e disponíveis, mantendo apenas o botão Atualizar agora para instalar na pasta existente.
- Atualizador anônimo para clientes; nenhuma credencial do proprietário é incorporada no aplicativo.
- A janela Windows e os visores de RANK/fusões passam a respeitar a área útil do monitor; tamanho mínimo antigo de 1100 × 700 removido para suportar orientação vertical.
- Pop-ups de cartas e atualizações cabem em janelas estreitas ou baixas, mantendo rolagem interna, foco e controles da janela.
- Leitura da mão com validação dupla de cinco cartas, cache temporário por processo e proteção contra endereços de memória ambíguos.
- Oponentes e projeção experimental de RANK X15 reutilizam a base de RAM detectada, sem alterar as fórmulas nem validar automaticamente uma ISO.
- Mantido o botão único **Atualizar agora**: substitui os arquivos na pasta atual, reinicia o DUELTRACE e preserva os dados locais.
- Release Preview e ZIP estável usam a mesma validação de origem, tamanho, SHA-256 e identidade do build antes da instalação.
- Pesquisa em fusões aceita IDs com `#`, ignora acentos e atualiza a paginação ao trocar de filtro.
- Painel de atualizações mais simples, com ações de atualizar e visualizar novidades.
- Pacotes ZIP verificados substituem o aplicativo na pasta existente e reiniciam o DUELTRACE.

## Correções
- **Janela principal (Windows):** substituído o arraste CSS e o movimento por eventos WebView2 pela rotina nativa Win32 de arraste da janela na thread da interface. Botões da janela permanecem clicáveis e o redimensionamento lateral continua preservado.
- **Janela principal:** toda a faixa superior do DUELTRACE pode ser usada para clicar e arrastar a janela, inclusive sobre o logotipo; botões de atualização, minimizar, maximizar e fechar continuam independentes.
- **Canal de distribuição:** quando o servidor público ainda não estiver configurado, o aplicativo mostra uma mensagem objetiva sem solicitar credenciais.
- **Janela sem barra de título:** restauração das bordas nativas de redimensionamento do Windows; agora deve ser possível arrastar laterais e cantos, sem alterar o visual do cabeçalho.
- **Atualizações:** painel de versões centralizado, fora da rolagem que escondia conteúdo; mensagens claras quando a distribuição pública estiver indisponível.
- **Mão ao vivo no ePSXe:** uma cópia estática com cinco IDs plausíveis não é mais tomada como a mão verdadeira. O DUELTRACE aguarda uma mudança real de carta entre consultas antes de confirmar o endereço, enquanto continua procurando outros candidatos.
- Quando a leitura confirmada fica inválida, o programa deixa de exibir cartas e reinicia a busca automaticamente; endereços e observações provisórias permanecem somente na memória desta execução.
- Varredura de RAM agora prossegue mesmo quando encontra duas cópias estáticas da mão, sem repetir as mesmas posições indefinidamente.
- ePSXe: a varredura de RAM continua de onde parou quando o primeiro bloco de 48 MB não contém a mão; busca rápida pelos deslocamentos PS1 e mensagens de estado mais claras.
- Endereço físico fixo da RAM não impede mais o reconhecimento de mãos em versões do ePSXe com disposição de memória diferente.
- Resolvida a dependência de releases privadas para atualizações dos clientes, mantendo o repositório de desenvolvimento fechado.
- Atualização estável portátil tem prioridade quando também existe uma Preview.
- Testes da interface atualizados para o novo fluxo de atualização.

