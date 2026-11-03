# DUELTRACE WebUI 0.7.0 — correção do layout sem CSS

## Sintoma relatado e reproduzido
Nas capturas do Windows, a WebUI apresentava fundo escuro com gráficos/vetores enormes, links azuis comuns, fontes Times New Roman e cartões de coleção em tabelas sem grid. O painel confirmou o motor Python conectado e a leitura de 722 cartas; o problema estava no visual, não na importação de ISOs.

## Causa confirmada no ZIP anterior
Foi examinado o próprio arquivo `DUELTRACE-WebUI-Windows-Preview.zip` distribuído.

- `_internal/web/out/index.html` inclui um CSS sob `/_next/static/chunks/*.css`.
- O CSS está presente no pacote, mas tem apenas **9.275 bytes**.
- Os seletores essenciais `.flex` e `.grid` não existem.
- O arquivo contém regras Tailwind não compiladas, como `@apply`.
- O projeto importava `tailwindcss` em `globals.css`, mas não possuía `postcss.config.mjs` nem a dependência `@tailwindcss/postcss`.

O Next.js considerava o build bem-sucedido porque a falta do plugin não era tratada como erro de exportação.

## Correção
1. Adicionado `web/postcss.config.mjs` com o plugin oficial `@tailwindcss/postcss`.
2. Adicionada dependência fixa `@tailwindcss/postcss@4.3.4` e sincronizado `web/package-lock.json`.
3. Adicionado `tools/security/verify_web_css.py`, que **bloqueia a geração do executável** se o CSS for curto demais, contiver diretivas `@apply`/`@theme`, não tiver classes de layout, ou não for servido com status 200 e MIME `text/css` pelo próprio servidor localhost.
4. Os gates já existentes de auditoria npm/pip, Microsoft Defender, SBOM e SHA-256 permanecem obrigatórios.

## Regra de publicação
- Não atualizar automaticamente a Alpha 0.6.6/Tkinter.
- Testar nova compilação da WebUI em pasta separada, mantendo o Chrome Safe Browsing e Defender ativados.
- Ainda não há certificado de assinatura digital e o pacote é **experimental**. Se for classificado como malicioso, interromper a instalação.
- Após validar os estilos no PC real, avaliar DPI, dimensionamento, responsividade e funcionamento com ePSXe antes do lançamento oficial.
