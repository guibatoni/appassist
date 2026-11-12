# DUELTRACE — Notas da atualização

## Novidades
- **Biblioteca de Drops:** filtros de recompensa **BCD-POW** e **BCD-TEC** agrupam B, C e D, sem alterar os RANKs individuais dos duelos. Remaster X15 mantém Z-POW, S-POW e S-TEC.
- **Atualização pelo aplicativo:** a Preview é consultada em GitHub Releases e instalada pelo botão **Atualizar agora**, com validação SHA-256, substituição na mesma pasta e reinício automático.
- **Interface adaptável:** o DUELTRACE reorganiza navegação, cartas, fusões, drops e detalhes em telas 9:16, 16:9, 16:10, 4:3 e ultrawide, sem distorcer as cartas.
- **ePSXe:** busca dinâmica de RAM quando o endereço antigo não funciona, com suporte a executáveis identificados por número de versão (somente Windows).
- Atualizações privadas podem ser encontradas pelo mesmo botão quando o proprietário já autenticou o GitHub CLI no Windows.
- Aba Fusões: escolha pesquisar por **resultado final**, **material da fusão** ou **ambos**, por nome ou ID da carta.
- Patch notes exibidos em uma janela dentro do aplicativo, sem abrir o navegador.

## Melhorias
- Atualizador mostra os números reais dos builds Preview instalados e disponíveis, mantendo apenas o botão Atualizar agora para instalar na pasta existente.
- Localização opcional do GitHub CLI nas pastas padrão do Windows, inclusive quando o app foi aberto pelo Explorador de Arquivos com PATH antigo.
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
- **Janela principal (Windows):** substituído o arraste CSS do WebView2 que não funcionou por movimento real do pywebview (`Window.move`) enquanto o botão esquerdo é mantido pressionado na faixa superior. Botões da janela permanecem clicáveis e o redimensionamento lateral continua preservado.
- **Janela principal:** toda a faixa superior do DUELTRACE pode ser usada para clicar e arrastar a janela, inclusive sobre o logotipo; botões de atualização, minimizar, maximizar e fechar continuam independentes.
- **Atualizações privadas:** quando não houver autenticação no GitHub CLI, a janela mostra instruções práticas (`gh auth login` e `gh auth status`) com aviso, em vez de um sinal de sucesso enganoso.
- **Janela sem barra de título:** restauração das bordas nativas de redimensionamento do Windows; agora deve ser possível arrastar laterais e cantos, sem alterar o visual do cabeçalho.
- **Atualizações:** painel de versões centralizado, fora da rolagem que escondia conteúdo; mensagens claras quando o acesso ao GitHub privado não está configurado.
- **Mão ao vivo no ePSXe:** uma cópia estática com cinco IDs plausíveis não é mais tomada como a mão verdadeira. O DUELTRACE aguarda uma mudança real de carta entre consultas antes de confirmar o endereço, enquanto continua procurando outros candidatos.
- Quando a leitura confirmada fica inválida, o programa deixa de exibir cartas e reinicia a busca automaticamente; endereços e observações provisórias permanecem somente na memória desta execução.
- Varredura de RAM agora prossegue mesmo quando encontra duas cópias estáticas da mão, sem repetir as mesmas posições indefinidamente.
- ePSXe: a varredura de RAM continua de onde parou quando o primeiro bloco de 48 MB não contém a mão; busca rápida pelos deslocamentos PS1 e mensagens de estado mais claras.
- Endereço físico fixo da RAM não impede mais o reconhecimento de mãos em versões do ePSXe com disposição de memória diferente.
- Corrigida a limitação da consulta anônima que não enxerga Releases do repositório privado quando há GitHub CLI autenticado disponível.
- Atualização estável portátil tem prioridade quando também existe uma Preview.
- Testes da interface atualizados para o novo fluxo de atualização.

