# DUELTRACE v0.9.7 — auditoria das dependências web

## Resultado observado nesta execução

- `npm audit --omit=dev --audit-level=moderate`: nenhuma vulnerabilidade de produção.
- A auditoria completa encontra **8 pacotes de desenvolvimento afetados**, todos derivados de um único advisory: [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), de severidade moderada.
- `npm audit --audit-level=high` continua aprovando o limite configurado pelo CI; isso não significa ausência de achados moderados.
- `npm ls minimatch --omit=dev --all` não encontra `minimatch` na árvore de produção.

O advisory descreve possível negação de serviço por amplificação de partes de
um padrão glob. A faixa reportada é `minimatch >=7.0.0 <11.0.1`.

## Caminho afetado e ausência de patch compatível

```text
eslint-config-next 16.4.4
└─ typescript-eslint 8.72.1
   └─ @typescript-eslint/typescript-estree 8.72.1
      └─ minimatch 10.2.6
```

Na consulta ao registro npm, `8.72.1` é a versão estável mais recente de
`@typescript-eslint/typescript-estree`, que declara `minimatch: ^10.2.2`.
`10.2.6` é a versão mais recente da linha 10 e continua na faixa afetada.
A correção do advisory começa em `11.0.1`; a versão 11 mais recente observada
é `11.0.4`.

`npm audit fix --dry-run --json` não encontrou atualização compatível: nenhuma
adição, remoção ou alteração foi proposta sem forçar mudanças. A sugestão de
correção da auditoria aponta para `eslint-config-next 15.5.29`, uma mudança de
major para trás que faria a configuração divergir de Next.js `16.4.4`.
Não foi aplicada. Tampouco foi imposto um override de `minimatch` 11 fora da
faixa que o consumidor declara suportar.

Os manifests e o lockfile permanecem inalterados por esta investigação. Não
foram usados `--force`, supressões de advisory ou desativação de verificações.

## Exposição e acompanhamento

O caminho identificado pertence ao ferramental de lint/TypeScript. A chamada
observada em `typescript-estree` corresponde a padrões de configuração de
`allowDefaultProject`; não é uma rota que recebe nomes de cartas, ISOs ou
respostas do Ollama. Esses pacotes não são dependências de produção do
aplicativo estático. Isso reduz a exposição do cliente, mas não elimina o
achado no ambiente de desenvolvimento e CI.

Até existir uma atualização compatível, tratar configurações e padrões glob
de contribuições externas como entrada não confiável, executar ferramentas de
análise em runners isolados e evitar executar lint com padrões fornecidos pelo
usuário do aplicativo. Manter as auditorias existentes e seu relatório visível.
O achado não foi resolvido e deve continuar listado nas limitações da entrega.

Para encerrar esta pendência: quando `typescript-eslint` publicar uma versão
estável que aceite uma versão corrigida de `minimatch`, atualizar o lockfile
dentro das faixas suportadas, executar `npm ci`, as duas auditorias, tipagem,
lint e build, e registrar os resultados. Uma migração major deliberada exige
validar compatibilidade do consumidor; não deve ser feita apenas para zerar
o relatório de segurança.
