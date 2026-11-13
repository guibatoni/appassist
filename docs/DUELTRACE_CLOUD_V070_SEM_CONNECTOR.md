# DUELTRACE Cloud v0.7.0 — sem Connector

## Decisão de arquitetura

A interface online padrão deixa de depender de Windows Connector, Python, Node.js local, chave temporária ou acesso HTTP a `127.0.0.1`. O DUELTRACE Cloud abre no navegador via `https://dueltrace-cloud.vercel.app/`.

A nova tela em `web/public/cloud-online/` carrega arquivos estáticos da Vercel: `index.html`, `app.css`, `app.js`, `iso-scanner.js` e `catalog-store.js`. As permissões do navegador permitem selecionar ISO/BIN pelo input `type=file`; os bytes são analisados **no navegador**, nunca enviados para o servidor. CSP do site impede `fetch` e conexões de rede externas nesta interface.

## Fluxo de uso

1. Abra a URL pública em computador, tablet ou celular compatível.
2. Clique em **Importar ISO/BIN** e selecione um arquivo ao qual esse dispositivo tenha acesso, **sem enviá-lo à hospedagem**.
3. O leitor reconhece ISO9660 nas geometrias 2048, RAW 2352 (Mode 1/2), 2336 e 2448, inspeciona um executável `PS-X EXE` e verifica o layout conhecido de nomes/atributos FM.
4. Se a estrutura for coerente, ele salva **somente o catálogo normalizado** de cartas/oponentes no IndexedDB do navegador, separado da ISO original.
5. Navegue pela biblioteca, pesquise cartas, veja detalhes ATK/DEF/tipo, monte deck manual por mod e simule uma mão manual de até cinco cartas.
6. **Exportar JSON** cria um arquivo de catálogo sem binários. Para transportar seus dados a outro dispositivo, importe esse JSON lá.

## Limites preservados

- A ISO/BIN não é persistida, enviada nem compartilhada. O navegador lê somente o arquivo selecionado; o IndexedDB mantém o catálogo derivado.
- A análise binária reconhece inicialmente o layout **FM conhecido**. Mods com tabelas realocadas, compactadas ou reestruturadas exigem novos decodificadores. Não há aprovação universal de 722 cartas, nomes ou adversários sem evidência.
- Não foram portados os decodificadores completos de arte, fusões, drops, scripts de efeito e ranking modificado. Quando indisponíveis, a interface mostra a limitação, não inventa valores.
- Fusões/drops presentes em um JSON importado são classificados como **não verificados**, até mecanismo de procedência adicional.
- RANK e mão em tempo real do ePSXe **não** são lidos: um site remoto não consegue inspecionar a RAM de outro programa/processo instalado no PC sem integração local. Sem Connector, o modo de duelo atual é manual. Para leitura automática 100% web, seria necessário um emulador no navegador e uma integração legal/compatível com seu estado.
- IndexedDB é **armazenamento por dispositivo e navegador**, não um banco de dados compartilhado nem sincronização online. Contas/usuários + banco de dados + storage/consentimento exigem fase separada.
- A publicação do site não autoriza redistribuir ISOs, BINs, artes, músicas ou ativos de terceiros.

## Segurança

- CSP de `/cloud-online/*` com `connect-src 'none'`, scripts e CSS apenas do mesmo domínio, sem iframes e sem envio de formulários.
- Sem tokens, login, armazenamento de credenciais ou dependência do Connector.
- Sem `fetch` nos scripts online. `File.slice` e `File.text` lidam apenas com arquivos escolhidos explicitamente.
- Limites de leitura ISO: arquivos de até 2 GiB; executáveis até 8 MiB; números máximos de diretórios, arquivos e bytes. Extensões diferentes são rejeitadas.
- Identificação estrutural e avisos conservadores para mods não reconhecidos; arte original não é distribuída no site.
- Teste Node com discos **sintéticos** cobrindo ISO 2048, BIN 2352, 722 cartas/39 adversários em layout conhecido, rejeição de formatos inválidos e ausência de chamadas ao Connector.
- Testes Python de regressão do motor legado permanecem para evitar alterações imprevistas no desktop, mas não são requeridos pelo site público.

## Roadmap futuro sem Connector

1. Adaptadores totalmente browser para famílias de mods realocadas, fusões e drops, com verificação por estrutura e evidência.
2. Catálogos e imagens autorizadas disponibilizados pelo serviço online sem a exigência de selecionar ISO, respeitando as licenças de terceiros.
3. Contas opt-in, banco de dados hospedado, autorização por usuário e sincronização segura de catálogos extraídos, backups e exportação/apagamento.
4. Emulador web independente (somente conteúdos e ROMs que o usuário possa usar legitimamente), com memória e estado disponíveis dentro do navegador; definir comportamento de RAM e RANK sem promessa falsa de integração com ePSXe externo.
5. Testes reais no Chrome/Edge/Firefox e dispositivos móveis com formatos de ISO e mods variados.

## Como validar a entrega

- GitHub Actions: `validar-cloud-local-first.yml` compila Next.js/export estático, verifica scripts via `node --check`, executa `node --test web/tests/cloud_browser_scanner.test.cjs` e testes Python.
- Vercel: build da branch `feature/dueltrace-cloud-v0.7.0-no-connector` e resposta HTTP 200 de `/`, `/cloud-online/`, `iso-scanner.js`, `catalog-store.js`, `app.js`.
- Teste final com ISO real do usuário ainda necessário.

Essa implementação **remove a dependência de Connector para as funcionalidades disponíveis**, mas não equivale a um banco de dados cloud compartilhado nem reproduz toda a versão Windows.
