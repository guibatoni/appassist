# DUELTRACE Web + ePSXe — arquitetura sem PCSX-Redux

## Situação verificada em novembro de 2026

O ePSXe Windows não possui uma API HTTP/REST/WebSocket pública de leitura de RAM que tenhamos conseguido confirmar em documentação oficial. Ele possui uma arquitetura de plugins PSEmu Pro usada para GPU/SPU/CD-ROM, e suporte histórico a netplay, mas nenhuma dessas funções equivale a um endpoint remoto para consultar a RAM do duelo.

Documentação consultada:
- https://www.epsxe.com/ — recursos oficiais e compatibilidade de plugins
- https://documentation.help/ePSXe/graphicapis.htm — interface de plugins PSEmu Pro
- https://documentation.help/ePSXe/commandlineswitches.htm — linha de comando/debug, sem endpoint HTTP de RAM
- https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging — extensão Chrome exige host nativo instalado
- https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access — requisitos e permissões para acesso ao loopback pelo navegador
- https://supabase.com/docs/guides/realtime/authorization — canais privados com RLS e JWT
- https://supabase.com/docs/guides/realtime/broadcast — envio seguro e recepção web de eventos

**Não é possível um site remoto ler memória de qualquer processo Windows apenas por JavaScript.** Para o ePSXe já instalado, precisa existir um módulo nativo autorizado pelo usuário que extraia e exponha somente dados derivativos. O usuário não precisa instalar um Connector separado se essa função for incorporada ao DUELTRACE Windows existente; ainda assim precisa executar esse aplicativo para ter os dados do jogo enquanto o ePSXe roda.

## Caminhos técnicos, em ordem de risco

### A. Integrar à versão DUELTRACE Windows que já funciona com ePSXe — recomendado

Fluxo:
1. ePSXe executa a ISO/BIN e o duelo no computador do jogador.
2. DUELTRACE Windows existente lê RAM com `dueltrace_live_hand.read_hand_from_epsxe` e `dueltrace_rank_live`. A leitura deve continuar **read-only**, restrita ao processo e validada contra o mod/ISO selecionado.
3. Converter resultados exclusivamente em um snapshot pequeno por `scanner/dueltrace_epsxe_web_snapshot.py`.
4. Quando o usuário clicar em **Ativar modo web ao vivo**, iniciar um canal de saída TLS autenticado. Nunca subir servidor HTTP aberto no PC; sem redirecionar portas no roteador.
5. O navegador (no mesmo PC ou em celular) assina somente a sessão privada da conta e recebe snapshots quando houver. O site offline de bibliotecas continua independente de qualquer executável.
6. Ao encerrar o jogo, fazer logout, expirar sessão ou invalidar a leitura, o canal notifica indisponibilidade e apaga o snapshot recente.

O transporte pode ser Supabase Realtime Broadcast privado (com políticas RLS por usuário/sessão e credenciais somente do próprio usuário) ou outro provedor de WebSocket autenticado. Não usar canal público/sem autenticação. Não colocar `service_role`/segredos administrativos em código cliente. A escolha do provedor e habilitação de serviços, preços e autenticação exige aprovação explícita.

**Estado:** contrato JSON local implementado e testado sem rede na v0.19.2. **Transporte/sincronização/contas ainda não implementados.**

### B. Plugin nativo carregado pelo ePSXe — pesquisa futura, sem outro aplicativo em execução

Um plugin PSEmu Pro carregado pelo ePSXe poderia, em teoria, obter acesso à memória do processo e publicar uma API de telemetria read-only. Mas a API PSEmu Pro não garante acesso direto à RAM do CPU do PS1; plugins gráficos/som não são uma API de diagnóstico. Um wrapper de GPU, PAD ou SPU poderia comprometer vídeo, áudio, controles ou compatibilidade de mods. Não usar DLL injection como padrão ou alterar plugins existentes sem consentimento e teste real.

Um protótipo só é aceitável se:
- Passar nos testes com ePSXe original e mods reais;
- Não substituir indiscriminadamente plugin do usuário;
- Ser assinado, desinstalável e habilitado explicitamente;
- Não alterar memória do jogo ou abrir rotas de escrita;
- Oferecer autenticação local e bloquear conexões externas.

**Estado:** hipótese, não implementado nem verificado com ePSXe 2.x. Não assumir que funcionará.

### C. Extensão Chrome + Native Messaging

Uma extensão pode conversar com um host Windows. Porém o host **precisa ser instalado no PC**; o JavaScript da página não acessa diretamente o processo. Essa abordagem seria compatível com um DUELTRACE Windows que funcionasse como native host, mas exige extensão + manifesto + autorização; portanto não atende à interpretação de “nada instalado além do ePSXe”.

## Contrato de evento mínimo v1 (implementado só como estrutura Python)

```json
{
  "schema": 1,
  "type": "dueltrace.epsxe.duel.snapshot",
  "emulator": "epsxe",
  "sequence": 9,
  "hand": {"ready": true, "cardIds": [461,16,635,10,123]},
  "rank": {"ready": true, "score": 95, "category": "Z-POW", "provisional": true},
  "runningIsoConfirmed": false
}
```

Não incluir caminhos de disco, nomes de arquivos, PID, processos, endereço RAM, BIOS, ISO/BIN original, Memory Card, dumps ou chave local. O `runningIsoConfirmed` é `false` porque o ePSXe não fornece confirmação automática de que a imagem ativa no DUELTRACE corresponde à imagem carregada no emulador. Dados provisórios nunca devem aparecer como resultados oficiais.

**Aviso:** este contrato não é uma API de rede já disponível; é uma função pura para utilização em futura integração autorizada.

## Próxima implementação executável

1. Validar v0.19.2 Windows apenas com ePSXe (o aplicativo não terá PCSX-Redux).
2. Testar snapshots gerados com ePSXe 2.0.x e mods diferentes sem enviar informações para fora do PC.
3. Implementar, de forma opcional, autenticação e sessão privada no Cloud (nunca expor RAM bruta).
4. Adicionar opt-in **Compartilhar duelo no Cloud** dentro do DUELTRACE Windows, com botão inequívoco para parar.
5. Criar vista web para atualização de 1–2 snapshots/s, reconexão, timeout, contador e cancelamento de sessão.
6. Opcionalmente pesquisar plugin dentro do ePSXe para eliminar a necessidade do DUELTRACE Windows ativo, após a validação de compatibilidade.

## Requisitos de segurança e privacidade

- Por padrão, **off**: nenhuma transmissão da v0.19.2.
- Sem upload de ISO, BIN, RAM bruta, Memory Card, nomes de processos ou endereços.
- Apenas eventos validados e de tamanho fixo, com limite de frequência.
- Autenticação por usuário e canal privado isolado; rotação e revogação de sessão.
- Todos os canais de saída devem usar TLS e bloquear redirecionamento a hosts inesperados.
- Nunca expor um servidor local de ePSXe diretamente à internet, nem fazer injeção DLL sem teste/consentimento.
