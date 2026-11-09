# DUELTRACE Commercial Lite — Etapa 40: ativação integrada e edição isolada

## Implementado
- Executável separado `DUELTRACE-Commercial.exe` iniciado pelo entrypoint
  `scanner/dueltrace_commercial_entry.py`, sem modificar o entrypoint Alpha.
- A edição comercial consulta a licença assinada Ed25519 no AppData em cada
  chamada privilegiada do motor Python; um modal React sozinho não seria proteção.
- Estado de licença / geração de pedido / importação de licença são as únicas
  operações comerciais permitidas antes da ativação, além de fechar a janela.
- A interface permite criar e copiar ou salvar `DUELTRACE-pedido-ativacao.json`,
  encaminhá-lo ao suporte Batoni Dev e importar `license.json` pelo seletor.
- Nenhum IP, ID bruto do Windows, ISO, ROM ou memória do ePSXe é enviado
  automaticamente. O pedido contém um hash pseudônimo do dispositivo.
- O modal é interno, com fundo escurecido e desfocado, explicações simplificadas,
  foco por teclado e aviso de erro quando a licença não é válida.
- O motor bloqueia também a leitura de artes geradas por endpoint local enquanto
  a licença comercial não estiver ativa.
- Instalador NSIS em `%LOCALAPPDATA%\Programs\DUELTRACE-Commercial`,
  separado do ZIP Alpha/Preview e sem exigir elevação de administrador.
- No Commercial Lite, o atualizador **do canal Alpha fica bloqueado e oculto**:
  nunca deve instalar pacotes que substituam o executável comercial por Alpha.
  O canal seguro de atualizações comerciais é tarefa futura.

## Fluxo do cliente (quando autorizado comercialmente)
1. Receber o instalador oficial do canal de distribuição aprovado.
2. Instalar e abrir o DUELTRACE Commercial Lite.
3. Clicar em `Gerar pedido de ativação`, depois `Copiar pedido` ou
   `Salvar pedido` e enviar o JSON ao suporte Batoni Dev, com comprovante de compra.
4. A Batoni Dev emite manualmente a licença usando a chave PRIVADA mantida offline
   (ver `DUELTRACE_COMMERCIAL_LITE_V39.md`).
5. O cliente recebe um arquivo `license.json` e escolhe `Selecionar licença`.
6. A assinatura e o dispositivo são validados localmente, os dados de ativação
   ficam em AppData e a janela reinicia liberando as funções.

## Reinstalação e mudança de PC
- Reinstalação na mesma máquina mantém a licença em AppData, fora da pasta
  removida pelo desinstalador.
- Troca de computador: enviar novo pedido; Batoni Dev reemite após verificar a
  compra e atualizar seu controle de ativações offline. **Excluir licença local
  NÃO revoga licenças já distribuídas.**
- Para dois computadores por compra, emitir duas licenças de dispositivos
  diferentes e registrar manualmente ambos. Não há controle central automático.

## Bloqueios para lançamento comercial
1. Gerar o par definitivo Ed25519 em computador seguro/offline, armazenar
   backup cifrado da chave PRIVADA e configurar só a chave PÚBLICA no build.
   Atualmente `PUBLIC_KEY_B64` é propositalmente vazia: **nenhuma licença
   comercial real pode ser ativada no protótipo**.
2. Assinatura digital Authenticode do executável e instalador e testes
   do SmartScreen, ou um plano transparente que não exija o desligamento de
   proteções do Windows. Assinatura de licença não substitui assinatura de código.
3. Canal de atualização compatível e autenticado para Commercial Lite,
   com backup/rollback e instalador versionado. Atualização Alpha é bloqueada.
4. Validar GUI de ativação e testes de instalação silenciosa e visível em Windows
   real, reinício, RANK, pop-ups, ePSXe, licenças em AppData e desinstalação.
5. Revisar segurança das dependências, artefatos, escopo de dados pessoais e LGPD.
6. Revisar direitos autorais, uso de marcas e artes do jogo antes de qualquer
   comercialização.

## Estratégia de custo
Sem API de licença nem hospedagem recorrente, o custo fixo de infraestrutura
pode permanecer zero, mas Patreon e intermediários de pagamento cobram taxas.
Não existe serial por IP nem DRM impossível de contornar. O suporte manual
inclui reativação após mudança de dispositivo, controle da compra e atendimento.

## Comandos para QA
```powershell
python -m unittest discover -s tests -p "test_dueltrace_commercial*.py" -v
python -m unittest discover -s tests -p "test_*.py"
```

O CI nesta branch gera, instala, reinstala e remove um **instalador NSIS de
TESTE**, em runner descartável, verifica preservação do AppData e roda o
Microsoft Defender. O setup não é publicado e não possui chave pública
comercial definitiva.
