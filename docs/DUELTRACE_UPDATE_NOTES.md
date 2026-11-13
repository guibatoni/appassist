# DUELTRACE v0.19.0 — Preview

## Novidades
- Integração ao PCSX-Redux Windows pela API HTTP nativa, independente dos endereços de RAM do processo Windows.
- Seleção de emulador ePSXe, PCSX-Redux ou detecção automática em Configurações.
- Porta do PCSX-Redux configurável e diagnóstico de conexão sem ler arquivos externos.
- Leitura de mão do PS1 de 2 MiB ou 8 MiB pelo PCSX-Redux; exige mudança real de cartas antes de confirmar.

## Melhorias
- Mantidos todos os recursos do ePSXe, Biblioteca de Mods, fusões, imagens e configurações da v0.18.0.
- Início opcional do PCSX-Redux com a ISO/BIN do mod ativo, utilizando flags oficiais sem alterar configurações do emulador.
- Reconexão e descarte de mão antiga quando a RAM ou a sessão deixam de ser válidas.
- O DUELTRACE não faz POST ao servidor do PCSX-Redux, não escreve na RAM e não envia dados do jogo para a nuvem.
- Consulta estrutural provisória de RANK X15 na RAM PS1; cálculos de outros mods permanecem bloqueados até validação própria.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Não permitida a distribuição do aplicativo sem autorização expressa do desenvolvedor.

## Correções
- Endereços Windows do ePSXe não são usados por engano no PCSX-Redux.
- A preferência de emulador é salva sem sobrescrever as ISOs, decks ou backups.
- Versões PCSX-Redux sem as rotas HTTP esperadas exibem indisponibilidade, não leituras falsas.
- A conexão é limitada ao endereço local 127.0.0.1, com limite de bytes e bloqueio de redirecionamentos.

## Limitações
- O PCSX-Redux deve oferecer GET /api/v1/execution-flow e GET /api/v1/cpu/ram/raw e ter o Web Server habilitado manualmente.
- Por padrão o Web Server do PCSX-Redux pode escutar em todas as interfaces; restrinja a porta no firewall antes de ativar.
- Cada build histórica do PCSX-Redux ainda precisa de validação com emulador/ISO real; testes automatizados usam RAM sintética.
- RANK ao vivo por ISO, drops, oponentes e identidade do jogo em execução só são exibidos conforme validação do próprio mod.
- O DUELTRACE não confirma automaticamente que a ISO carregada no PCSX-Redux é a mesma ativada na biblioteca.
