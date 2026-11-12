# DUELTRACE Cloud v0.2.2 — diagnóstico de clique e pareamento

## Falha reportada
O usuário continuou sem reação perceptível ao clicar em **Conectar ao computador** mesmo após v0.2.1. A execução real no Windows ainda não foi observada nesta revisão; o objetivo é tornar a falha diagnosticável e deixar o botão acionável.

## Alterações
- Removido o bloqueio `disabled={busy||!clientReady}`; o botão só é desabilitado durante uma tentativa pendente.
- O botão passou a ser `type="submit"` dentro de formulário com `onSubmit`, cobrindo clique e tecla Enter sem handlers duplicados.
- Indicador visível **Cloud v0.2.2**, estado da inicialização JavaScript e número de cliques reconhecidos.
- O retorno **Clique recebido. Consultando o Connector** é mostrado antes da resposta da API.
- Erros de chave incompleta, conexão e autenticação são mostrados acima do botão, com contorno.
- Mantida leitura da chave diretamente no input DOM, sem armazenamento, logs, URLs ou envio a backend remoto.
- Testes de regressão atualizados para os novos controles.

## Como distinguir os problemas no Chrome
1. Se o indicador NÃO mostrar **Cloud v0.2.2**, a pasta/servidor frontend ainda contém versão anterior. Pare o `npm` e execute o site a partir desta branch. Considere limpar somente `web/.next`; não toque em ISOs, saves ou perfis.
2. Se mostrar **aguardando inicialização do JavaScript** indefinidamente ou o contador de cliques não mudar, há erro de hidratação/JavaScript ou um elemento bloqueando a interação; inspecione Console (F12).
3. Se os cliques aumentarem e aparecer erro de chave, a UI recebe o evento; use a chave da execução atual do Connector.
4. Se aparecer **Consultando o Connector...** e depois erro de conexão, verifique se o processo Python está ativo em `127.0.0.1:8765` e se o Chrome autoriza o acesso à rede local.
5. Se a autenticação funcionar, a tela navega para Biblioteca de Mods.

## Inicialização local
Na raiz do projeto, em terminais separados:

```powershell
python scanner/dueltrace_cloud_connector.py
```

```powershell
cd web
npm.cmd ci
npm.cmd run dev
```

Abrir `http://127.0.0.1:3000/cloud/`. O Chrome pode armazenar preenchimentos antigos; copiar a chave nova do terminal.

## Limites
O CI comprova testes estáticos/segurança/build, não um teste E2E real no Chrome do usuário. Não publicar como problema resolvido em campo antes de validar clique e conexão.
