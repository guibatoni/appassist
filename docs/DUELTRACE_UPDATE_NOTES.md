# DUELTRACE v0.19.4 — Preview

## Novidades
- Aba Decks apresenta os 15 blocos físicos do Memory Card PS1, distinguindo saves FM íntegros, slots vazios e outros jogos.
- Novo botão Selecionar outro Memory Card na aba Decks, para alternar entre os dois cartões do ePSXe.
- Origem das 40 cartas identificada claramente como Memory Card ou cópia local salva.

## Melhorias
- Deck mostrado no DUELTRACE usa o save selecionado e validado, sem ser substituído por dados suspeitos da RAM.
- Trocar explicitamente de Memory Card escolhe o save FM único do novo cartão quando for inequívoco.
- Snapshots automáticos ficam vinculados ao cartão selecionado; o deck do cartão anterior não aparece como atual.
- Mão, fusões, RANK, biblioteca, Memory Card e monitoramento em segundo plano continuam disponíveis.

## Correções
- Corrigida a substituição indevida das cartas do deck por 40 IDs encontrados em um endereço RAM estimado.
- Deck RAM só pode ser aceito como candidato corroborado após coincidir integralmente com um save íntegro.
- Saves inválidos ou de outros jogos aparecem como blocos não selecionáveis, sem interpretação falsa de cartas.
- Salvar deck usa apenas o Memory Card selecionado; nunca persiste RAM não validada como deck confirmado.
- O ePSXe continua sendo o único emulador e nenhum recurso PCSX-Redux é incluído.

## Limitações
- O cartão PS1 possui 15 blocos físicos, mas não necessariamente 15 saves. Cada arquivo mostra seus próprios blocos.
- A integridade do save não garante qual ISO ou mod está rodando atualmente no ePSXe.
- A posição do deck ativo na RAM exige confirmação adicional com um duelo real, sem dados presumidos.
- Arquivos de Save State do ePSXe não são saves de Memory Card e exigem análise separada.
- Nenhuma transmissão de RAM, HTTP/WebSocket ou modificação do Memory Card foi adicionada.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição somente com autorização expressa do desenvolvedor.
