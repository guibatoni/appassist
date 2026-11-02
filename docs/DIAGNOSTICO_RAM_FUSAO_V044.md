# Forbidden Memories MultiMod v0.4.4 — Diagnóstico de fusão pela RAM

## O que está comprovado
- O overlay lê 5 IDs de cartas da mão usando `rd.read(0xBFF484, 140)` em `painel_compacto.CompactPanel.tick()`.
- O usuário confirmou a fusão **Dragon Zombie + Yamatano Dragon Scroll → Skelgon** no ePSXe.
- As demais receitas que o usuário registrou no catálogo devem manter sua origem de evidência (revisada, observada no jogo etc.).
- Não conhecemos ainda o endereço da RAM que prova o resultado de uma fusão. Nenhuma alteração de bytes em uma região candidata é, por si só, essa prova.

## Nova aba Diagnóstico RAM
Na Biblioteca integrada ao overlay:
1. Selecione **a mesma ISO que está aberta no ePSXe** e ative-a na Biblioteca.
2. Durante um duelo com cinco cartas válidas na mão, abra **Diagnóstico RAM**.
3. Antes de realizar uma fusão, clique **1. Capturar ANTES**.
4. Volte ao jogo, execute **uma fusão real**, e espere um estado estável.
5. Opcionalmente, digite o **ID da carta resultante que observou no ePSXe**.
6. Clique em **2. Capturar DEPOIS**.
7. A interface salva automaticamente um relatório JSON no diretório:
   `%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\diagnosticos_fusao\<sha256_da_iso>\`
8. Compartilhe o arquivo JSON de uma sessão **com fusão real** e, idealmente, outra sessão de controle **sem fusão**, para comparar ruído de RAM e eventos de cartas.

## Funcionamento técnico
- Captura somente 236 bytes por amostra:
  - 0xBFF484, 140 bytes — mão com layout validado (5 registros de 28 bytes).
  - 0xB483A2, 32 bytes — região exploratória (não validada como fusão).
  - 0xB5B21E, 32 bytes — exploratória.
  - 0xB41891, 32 bytes — exploratória.
- Exige o **mesmo PID** do ePSXe e o mesmo SHA do catálogo entre as capturas.
- Mostra quantos bytes mudaram por região e exemplos das diferenças.
- O ID observado é uma anotação do usuário, **não uma identificação automática**.
- **Não** registra fusões confirmadas, não atualiza os catálogos de receitas e não modifica ROMs, emulador, Memory Cards ou saves.
- Não depende de Ollama. A IA local poderá ser usada posteriormente para investigar padrões, sem que isso seja considerado validação automática.

## Restrições
- É um **diagnóstico experimental**. Se as regiões escolhidas não refletirem a fusão, será necessário encontrar outros endereços específicos do ePSXe/mod.
- A seleção manual do perfil não comprova qual ISO está executando.
- Não realizar leitura completa de memória nem enviar ROM, saves ou Memory Cards.
- Testes CI utilizam leitores de RAM simulados. Teste real no Windows/ePSXe ainda pendente.

## Futuro
Após coletar amostras positivas (fusão conhecida) e negativas (sem fusão), buscar uma assinatura reproduzível:
- materiais consumidos → resultado,
- alteração temporal consistente,
- confirmação com múltiplos duelos e mods,
- registro automático somente quando houver evidência robusta.
