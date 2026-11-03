# DUELTRACE WebUI — visual v0 integrado ao aplicativo Windows

Interface feita no v0/Vercel, adaptada para ler **dados reais do motor Python do DUELTRACE** por meio do pywebview.

## Desenvolvimento do visual

Na pasta `web/`:

```powershell
npm ci
npm run dev
```

A versão aberta no navegador comum é **somente prévia visual**: não tem permissão para ler ROMs, perfis e RAM do ePSXe. Não existe backend público hospedado no Vercel com essas informações, e isso é intencional.

## Build para o Windows

```powershell
npm run build
```

O Next.js exporta HTML/CSS/JS estáticos para `web/out`. Depois:

```powershell
python -m pip install pywebview pillow
python scanner/dueltrace_web_desktop.py
```

O aplicativo abre a janela local baseada em WebView2. Para um executável distribuível sem CMD, use o artefato do workflow `Validar integração v0 DUELTRACE Windows` no GitHub Actions, que empacota os arquivos via PyInstaller.

A antiga Alpha v0.6.6/Tkinter continua disponível e não é substituída por esta prévia.

## Quatro telas ativas

- `/inicio/`: cinco slots da mão real e sugestões de fusões por dados extraídos
- `/mods/`: ISOs cadastradas, importação de arquivo local, ativação e ePSXe
- `/biblioteca/`: cartas de perfil com origem de efeito e imagens quando extraídas
- `/fusoes/`: catálogo paginado e procedência de cada receita

**Não utilizar** `lib/data.ts` nas telas públicas: esse arquivo foi gerado pelo v0 exclusivamente para visualização e contém cartas, efeitos e probabilidades fictícios. As quatro telas integradas usam `lib/desktop.ts`.

## Garantias e pendências

- O servidor interno atende apenas `127.0.0.1`; não expõe comandos HTTP de escrita.
- Comandos de importação, ativação e ePSXe passam pelo bridge local do pywebview.
- Nada é enviado automaticamente ao Vercel; nenhuma ISO ou memory card é distribuído.
- Ainda é necessário testar a janela, o seletor de arquivos e a RAM com o ePSXe real no Windows.
- Para detalhes, consulte `docs/DUELTRACE_V070_V0_INTEGRATION.md`.
