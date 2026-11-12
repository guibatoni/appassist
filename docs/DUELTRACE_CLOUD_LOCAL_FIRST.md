# DUELTRACE Cloud — protótipo local-first (0.1.0)

> Linha experimental isolada. O DUELTRACE Windows e suas releases 0.17.4/0.18.0 não são substituídos.

## Regra central de privacidade

**Nunca enviar ISO, BIN, Memory Cards, imagens binárias originais, dumps de RAM, endereços de memória, caminhos de arquivos nem tokens de pareamento para a nuvem.**

O site é somente uma interface estática. A extração de cartas, nomes, descrições, fusões, decks, oponentes e drops continua sendo feita pelo motor Python instalado no computador do jogador, exatamente como no DUELTRACE Windows. O navegador busca resultados derivados do Connector via loopback (`127.0.0.1`), sem uma API remota de dados do jogo.

| Informação | Origem/armazenamento atual | Pode ir para a nuvem? |
|---|---|---|
| ISO/BIN e executável PS1 | Disco do jogador | **Não** |
| Memory Card original e backups | Disco do jogador | **Não** |
| RAM e estado do ePSXe | Processo Windows | **Não** |
| Artes originais de cartas extraídas | Cache do jogador | **Não** |
| Nomes, atributos, descrições, fusões e drops | Derivados localmente, exibidos no navegador | **Não neste protótipo** |
| Conta, pagamento e situação da assinatura | Fora do escopo atual | Apenas metadados mínimos no backend futuro |
| Sincronização opcional de dados derivados | Fora do escopo atual | Somente com opt-in específico no futuro |

O Connector **não realiza chamadas HTTP para serviços externos**. Sua API aceita apenas requisições de um site autorizado e nunca recebe o conteúdo de uma ISO no corpo HTTP.

## O que existe nesta primeira entrega

- Página `/cloud/` do Next.js, estática e independente do desktop, com visual de Biblioteca, Fusões, Oponentes, Drops, Decks e Duelo ao vivo.
- Connector Python `scanner/dueltrace_cloud_connector.py` usando o motor já consolidado, sem reimplementar engenharia reversa.
- Importação local de ISO/BIN com **seletor nativo Windows**, não upload de arquivo pelo site.
- Seleção local de Memory Card com as mesmas regras conservadoras de validação do DUELTRACE.
- Alteração de ISO ativa por SHA-256 previamente cadastrado; não aceita caminhos enviados pelo navegador.
- Imagens HD fornecidas diretamente do cache local sob autenticação e bloqueio de caminhos externos.
- Mão/RANK apresentados usando os métodos existentes, com leitura periódica quando a aba está aberta.
- Token aleatório temporário por execução, enviado exclusivamente no header `Authorization`, não colocado em URL, cookie ou storage do navegador.
- CORS com origem exata, servidor vinculado apenas a `127.0.0.1`, sem wildcard, e resposta `no-store`.

## Teste no Windows (código-fonte)

Requisitos: checkout deste branch, Python 3.12+ com dependências já utilizadas pelo DUELTRACE e Node.js 22+.

Terminal 1, na raiz:

```powershell
python scanner/dueltrace_cloud_connector.py
```

O terminal exibe `http://127.0.0.1:8765` e uma chave temporária. A chave não é enviada a servidor e deixa de funcionar quando o processo é encerrado.

Terminal 2, na raiz:

```powershell
cd web
npm ci
npm run dev
```

Abra `http://127.0.0.1:3000/cloud/`. Clique em conectar, cole a chave, escolha a ISO local ou ative uma já cadastrada, consulte as seis abas e teste as operações no ePSXe.

A página atualmente precisa do **Connector Python** instalado/iniciado para fazer engenharia reversa e ler a RAM. O botão de importar usa `tkinter` no Windows. Não instala código no emulador.

### Futuro domínio HTTPS

Ao implantar a interface estática num domínio próprio, execute o Connector com a origem exata, por exemplo:

```powershell
python scanner/dueltrace_cloud_connector.py --origin https://SEU-DOMINIO-HTTPS
```

Não use `*` no CORS nem compartilhe o token. Desde versões recentes do Chromium, conexões de um site público HTTPS para `127.0.0.1` podem exigir consentimento explícito do navegador para rede de loopback. A primeira conexão deve ocorrer mediante clique do usuário.

## Itens a validar antes de qualquer assinatura mensal

1. Confirmar abertura de ISO, nomes, 722 cartas, imagens e fusões reais no Windows.
2. Confirmar Memory Card da ISO e decks com os blocos corretos; testar saves reais.
3. Validar o pareamento HTTPS ↔ Connector local em Chrome/Edge com prompt de loopback.
4. Validar mão e RANK do ePSXe no Chrome durante vários duelos e mods.
5. Auditar logs, limites de acesso, assinaturas digitais/atualizador do Connector e proteção contra execução de comandos remotos.
6. Só depois adicionar login, dispositivo, pagamentos e autorização periódica. **Não vincular assinatura ao acesso aos arquivos binários do usuário.**

## Status de implementação

Esta entrega é **um protótipo integrado em branch separada**, não uma release Windows assinada e não uma versão em produção. Nenhuma infraestrutura de conta, cobrança, nuvem de dados ou deploy público foi criada.
