# DUELTRACE v0.8.3 — Atualização GitHub e captura de RANK por duelo

Data: 03/11/2026 (Brasil).  
Repositório: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v083-updater-rank-capture`  
Base: `feature/dueltrace-v082-rank-duel-audit` (PR #32, commit `325e7884bd862830a94a11eb09a784e02aaab4dd`).

## Solicitação

> "crie um botão dentro do verificar atualizações para que o programa possa atualizar automaticamente a partir de novas versões dentro do github ... E continue com o foco em confirmar a RANK apresentada durante o duelo."

## Atualizador

A interface `web/components/shell/update-checker.tsx` agora exibe sempre o controle **Atualizar automaticamente pelo GitHub** dentro de Verificar atualizações. Ao clicar:

1. Consulta novamente as versões no GitHub.
2. Se não houver release estável mais recente com caminho seguro, explica por que a instalação está bloqueada.
3. Se o DUELTRACE instalado tiver assinatura Authenticode válida, uma release estável mais recente possuir instalador com digest SHA-256 e a origem corresponder ao repositório autorizado, pede consentimento.
4. A API `install_signed_update` faz NOVA consulta da release, baixa somente instalador da URL oficial, verifica hash e certificado do mesmo editor antes de iniciá-lo.

**Nenhuma Preview não assinada é instalada automaticamente**, nem se contorna SmartScreen/Defender. A versão Preview instalada hoje não é assinada, portanto o botão explica o bloqueio e oferece acesso manual à página oficial do build. Para distribuição comercial com atualização em um clique, ainda é necessário obter um certificado de assinatura de código válido e lançar instaladores estáveis assinados com a identidade correspondente. O aplicativo preserva os dados locais; o instalador final será responsável pelo upgrade do EXE.

A instalação é iniciada somente depois de clique e confirmação explícitos; não ocorre em segundo plano por mera verificação.

## Captura de RANK

- A Central de Duelo agora possui **Capturar previsão de RANK**, somente com score autorizável e LP confirmados.
- A ponte guarda um snapshot explícito da previsão, SHA, PID e timestamp; a API retorna só ID, score e letra, sem RAM ou PID.
- A captura é válida por 10 minutos, uso único, e cancelada quando o mod muda, LP divergem, leitura RAM falha, o processo do ePSXe muda ou o contador de turnos reinicia.
- A tela Drops apresenta a captura pendente e a envia junto com o resultado manual, com identificação explícita. Sem captura, o duelo é registrado sem projeção correlacionada.
- O painel Drops mostra os totais e últimas comparações: score + rank coincidentes, divergências, nota ausente e outras condições de vitória.
- O relatório JSON da v0.8.2 permanece disponível com a comparação por ISO.

**A fórmula do motor, os limites dos ranks, os contadores, as leituras RAM, os bindings, as tabelas de drops e os fluxos de fusões permanecem intactos.**

## Validação e pendências

- CI Windows: executar suíte completa Python, build Next.js e empacotamento seguro.
- Em duelos reais no ePSXe (Remaster X15, FM13, Original): verificar o hash da ISO local, confirmar qual ISO o emulador realmente executa, confirmar LP, capturar a projeção pouco antes da vitória, registrar rank e pontuação que aparecem no jogo e observar os resultados na aba Drops. Preferir pelo menos duas partidas independentes por configuração.
- Se o jogo não exibir pontos, registrar somente a letra; não inventar nota.
- Mods sem binding validado não podem obter score ao vivo nem captura.
- Captura + relato manual não é prova MIPS; exigir rastreamento dinâmico independente para afirmar cálculo real.
- Testes sintéticos não equivalem a validação de processo ePSXe real.
- Sem assinatura Authenticode comercial não ativar auto-instalação da Preview; não contornar avisos do Windows.

## Continuidade

> Continuar DUELTRACE a partir da versão 0.8.3, repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v083-updater-rank-capture`, baseada na v0.8.2 PR #32. A interface de atualizações possui botão persistente "Atualizar automaticamente pelo GitHub": só inicia release estável nova com SHA-256 publicado e assinatura Authenticode do MESMO certificado do aplicativo instalado, após confirmação; Previews não assinadas permanecem bloqueadas. Na Central de Duelo, o usuário captura a previsão RANK após confirmar LP; em Drops, associa a captura por ID ao resultado manual, registra pontos e rank, e vê divergências. Capturas têm expiração e são invalidadas em mudança de ISO, PID, reinício de duelo, LP divergente ou falha de RAM. Preserve a pontuação e o ranking X15/clássico da v0.8.1 e o relatório da v0.8.2. Confirmar HEAD, CI e PR antes de declarar sucesso. Próximo objetivo: validar tudo no ePSXe com X15, FM13 e Original, identificar independentemente qual ISO o ePSXe carregou e confrontar score e letras com resultado real e evidência MIPS. Não liberar novos mods sem binding validado, não distribuir ROM/SLUS/WA, não contornar SmartScreen, preservar scanner/biblioteca/fusões/drops/UI e atualizar documentação/branch/commit/PR/testes/pendências.
