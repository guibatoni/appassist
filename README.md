# DUELTRACE — MultiMod Companion

Assistente local para **Yu-Gi-Oh! Forbidden Memories (PS1)** e mods, em desenvolvimento para Windows. Projeto de fãs, não afiliado aos detentores do jogo. Não inclui nem distribui ISOs, saves ou recursos protegidos do jogo.

O aplicativo combina um motor Python com uma interface Next.js/React exportada estaticamente e exibida em uma janela pywebview/WebView2. A Alpha Tkinter permanece disponível como alternativa legada.

## Recursos e limites

- Biblioteca de Mods com importação local, SHA-256, cache e perfis separados por ISO.
- Biblioteca de Cartas, fusões e drops para estruturas que os parsers conseguem verificar.
- Início com mão, sugestões de fusão e RANK, condicionados à identidade da ISO e às evidências do leitor.
- Descoberta limitada de executáveis PS1 e contêineres renomeados, com diagnóstico para formatos desconhecidos.
- Comparação de cartas entre mods como candidaturas, sem copiar dados de jogo automaticamente.
- Ollama local opcional para investigação de evidências, sem aprovar informações automaticamente.
- Atualizações estáveis e Preview com controles de origem e integridade. A Preview pode não possuir assinatura de editor; consulte os avisos do pacote.

**Não há garantia de suporte universal.** Tamanho de arquivo, texto legível, pesos coerentes ou uma hipótese de IA não comprovam compatibilidade. O comportamento em jogo precisa ser validado por ISO e por layout RAM.

## Kit Windows de compilação e atualizações

O projeto inclui quatro arquivos `.cmd` na pasta raiz para verificar o ambiente,
**gerar o ZIP completo do DUELTRACE no Windows**, preparar um repositório público
separado de binários e publicar uma release assinada sem GitHub Actions.
Consulte [Guia do kit Windows v58](docs/DUELTRACE_KIT_WINDOWS_V58.md).

O ZIP completo não é gerado em Linux: ele depende do PyInstaller e do WebView2
no Windows. Releases para clientes exigem Authenticode e Microsoft Defender.

## Desenvolvimento

Python 3.10+ (CI: 3.12), com Tkinter para os módulos legados e Pillow para os testes gráficos. A interface usa o lockfile de `web/`; o CI utiliza Node.js 22.

```bash
python -m compileall -q scanner tests tools
python -m unittest discover -s tests -v
cd web
npm ci
npm run build
cd ..
python tools/security/verify_web_css.py
```

O build exporta as páginas para `web/out`. No Windows, instale as dependências descritas em [web/README.md](web/README.md) e execute:

```powershell
python scanner/dueltrace_web_desktop.py
```

`npm run dev`, dentro de `web/`, abre uma prévia no navegador sem acesso privilegiado às ISOs, perfis ou RAM. O desktop nativo WebView2 e o ePSXe exigem validação no Windows. A interface legada pode ser iniciada com `python scanner/abrir_biblioteca.py` (modo avançado: `--developer`).

## Investigação e continuidade

O [plano mestre](docs/DUELTRACE_MASTER_PLAN.md) descreve arquitetura, estado dos recursos e critérios para uma versão estável. O caso **GOG MOD 2.2** depende de evidências reais: os 39 nomes de oponentes, 722 cartas e 4.543 drops históricos não constituem um catálogo confirmado. O scanner preserva os candidatos e diagnósticos locais.

- [Interface e integração desktop](web/README.md)
- [Investigação de terminadores GOG](docs/DUELTRACE_V096_GOG_NAME_TERMINATORS.md)
- [Preservação dos drops provisórios](docs/DUELTRACE_V095_GOG_PROVISIONAL_DROPS.md)
- [Segurança](SECURITY.md)
- [Publicação e recursos legados](docs/PUBLICAR_RELEASE.md)

## Privacidade e confiança

O scanner lê os arquivos fornecidos pelo usuário sem alterá-los. Não envia ISOs ou memory cards à Internet. Perfis, nomes, fusões, drops e endereços RAM pertencem à ISO correspondente; não são transferíveis por igualdade de ID. Texto de efeito não comprova sua execução no jogo. Dados ausentes permanecem desconhecidos.

Ollama trabalha com relatórios limitados e é opcional. Os recursos locais essenciais não dependem dele. Atualizações consultam o GitHub mediante a ação correspondente; a interface não necessita de um backend público no Vercel.

Repositório: https://github.com/guibatoni/appassist
