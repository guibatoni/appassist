# DUELTRACE v0.19.2 — Preview (somente ePSXe)

## Reversão de compatibilidade
- Retirados integralmente os recursos PCSX-Redux adicionados nas versões experimentais 0.19.0 e 0.19.1.
- Base do aplicativo recuperada da versão Windows ePSXe v0.18.0, preservando o leitor de RAM, mão, fusões, LP, RANK, Biblioteca de Mods, cartas, decks, Memory Cards, visuais e ajustes de janela.
- O painel Configurações não oferece seletor PCSX-Redux, porta HTTP ou PID. Nenhum executável, servidor, conexão ou processo de PCSX-Redux é acessado pelo DUELTRACE.
- Os previews 0.19.0/0.19.1 não devem ser usados em futuras instalações; substitua pelo pacote v0.19.2.

## Preparação para API do ePSXe na versão web
- O DUELTRACE Windows continua utilizando exclusivamente a leitura local e validada de RAM ePSXe já existente, sem abrir portas HTTP.
- O website não pode consultar memória de processos Windows sem um componente local explícito. Não existe API oficial de RAM remota confirmada do ePSXe.
- Caminho recomendado para o futuro: uma API de eventos da partida emitida por um módulo nativo opcional, com autenticação e limites de dados; conexão de saída segura para o Cloud, sem transmissão de ISO/BIN ou dumps de RAM.
- Modo totalmente web sem qualquer módulo local permanece disponível para bibliotecas/catalogação; o acompanhamento automático de ePSXe instalado requer algum código nativo autorizado.

## Compatibilidade
- Focado no ePSXe Windows (incluindo 2.0.x) e mods suportados pelos perfis de RAM/ISO já testados pelo DUELTRACE.
- Não foram adicionados hooks, injeções, plugins ou serviços externos.
- As configurações e dados anteriores de ePSXe permanecem intactos.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Distribuição do aplicativo somente com autorização expressa do desenvolvedor.
