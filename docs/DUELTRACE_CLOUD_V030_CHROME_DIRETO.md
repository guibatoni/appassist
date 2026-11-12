# DUELTRACE Cloud v0.3.0 — Chrome direto, sem chave e sem Next.js

## Motivo
Na versão 0.2.2, capturas do usuário mostraram HTML renderizado, mas React nunca marcou a interface como iniciada (`Interface aguardando inicialização do JavaScript`). Campo de chave aparentemente preenchido não disparava eventos; o contador de cliques continuava zero. Alterar o handler React não resolve um navegador sem hidratação.

## Nova arquitetura de contingência e uso local

O próprio `scanner/dueltrace_cloud_connector.py` agora serve um painel HTML em `http://127.0.0.1:8765/local/`, sem JavaScript, React, Next.js, npm, WebView2 ou banco de dados. Abas, filtros, visualização de carta, fusões, drops, oponentes, decks, mão/RANK e formulários para ativar mod, importar ISO e selecionar Memory Card usam o motor Python existente, com navegação HTML tradicional.

O painel é oferecido **em adição** à interface Next.js experimental. Não é necessário apagar nem substituir a versão Windows ou a Cloud v0.2.2. Este modo é uma interface local no Chrome, **não** uma hospedagem remota e não implementa assinaturas.

### Execução com um único clique (Windows)

1. Baixar este branch e extrair o ZIP.
2. Dar duplo clique em `ABRIR_DUELTRACE_CLOUD.cmd` na raiz do projeto.
3. O script tenta Python do ambiente virtual, ou `py -3`, ou `python`.
4. O Connector inicia e abre o navegador padrão em `http://127.0.0.1:8765/local/`.
5. Se o Chrome não for o navegador padrão, copiar somente esse endereço (não contém segredo) e colar no Chrome. Não é preciso iniciar o Next.js.

Para desenvolvimento, o comando equivalente é:

```powershell
python scanner/dueltrace_cloud_connector.py --browser
```

A janela do Connector precisa permanecer aberta. Encerrá-la interrompe a leitura local. O pacote fonte ainda exige Python/dependências do projeto; **não** é um instalador Windows autoportante nem um exe.

### Segurança
- HTTP atende apenas `127.0.0.1`, exige cabeçalho Host correto e rejeita navegadores originados de páginas externas usando Origin e Sec-Fetch-Site.
- Painel aplica CSP sem JavaScript, sem recursos de rede externos e sem iframes, além de `X-Frame-Options: DENY` e `no-store`.
- A chave temporária continua existindo apenas dentro do processo e nos campos ocultos dos formulários. O jogador não precisa vê-la, copiar, colar, armazenar ou passá-la por URL.
- Ações POST exigem formulário do mesmo origin e token temporário CSRF com comparação segura. Nunca aceitam caminhos de arquivos da página: seleção ocorre no Windows.
- As rotas anteriores `/v1/*` continuam exigindo o token Bearer + origem autorizada.
- Exposição do painel é limitada ao loopback no próprio computador: ele não possibilita acesso remoto.

### Evidências e validação
Os testes `tests/test_dueltrace_cloud_browser.py` cobrem HTML sem JavaScript, navegação, consultas de dados filtrados, proteção contra HTML injection, CSRF/Origin/Host e isolamento da API anterior. O workflow `validar-cloud-local-first.yml` executa todos os `test_dueltrace_cloud_*.py` e compila a interface Next.js antiga.

O teste final deve ser no Windows com o Chrome real e uma ISO/Memory Card/ePSXe ativos. O CI Linux não comprova abertura do seletor nativo Windows nem leitura real de RAM.

## Nota sobre o futuro
Depois da validação local, distribuir o Connector empacotado como `.exe`, assinado se possível, com instalador e atalho; a experiência do usuário final não deve depender de Python instalado ou prompt aberto.
