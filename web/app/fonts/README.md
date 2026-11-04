# Fontes locais do DUELTRACE

Geist e Exo 2 preservam a tipografia da interface. Os arquivos variáveis originais
são distribuídos com o aplicativo e carregados por `next/font/local`. O build e
a execução não precisam consultar Google Fonts para obter essas fontes.
Ambas incluem os caracteres do português brasileiro e o eixo `wght` de 100 a 900.

Origem: repositório oficial [`google/fonts`](https://github.com/google/fonts),
commit fixo **`bbda7253fc363238b05d97515ca71f8ae49c4fa9`**. Os arquivos abaixo
foram baixados por HTTPS com verificação TLS, sem alteração do conteúdo.

| Arquivo local | Caminho na origem | SHA-256 |
| --- | --- | --- |
| `Geist-Variable.ttf` | `ofl/geist/Geist[wght].ttf` | `73894e0448cae90a92b6c2f8732b7bb9acb7b94c418bff559dad4a18e1de9659` |
| `Geist-OFL.txt` | `ofl/geist/OFL.txt` | `1781d2806a07d91c4edf4740b88449fab7d0eadad53f7c351b94cd4d4eb8c00f` |
| `Exo2-Variable.ttf` | `ofl/exo2/Exo2[wght].ttf` | `205a448676a2586f9c57c25f3d5c58ca8db7e6cf5edf7506783a010c6fe2bfb5` |
| `Exo2-OFL.txt` | `ofl/exo2/OFL.txt` | `7f95a8eeecc6904ffc81cd10cc8ebc7fcee72a67922924bf45f02dff03b88127` |

Os direitos autorais e a licença **SIL Open Font License 1.1** estão preservados
nos arquivos `Geist-OFL.txt` e `Exo2-OFL.txt`. Não vender as fontes isoladamente.
Manter os avisos e as licenças junto das fontes na distribuição e respeitar as
condições completas de cada arquivo.

Cópias idênticas das duas licenças ficam em `web/public/licenses/fonts/` para
serem incluídas automaticamente no export estático e no pacote Windows. Após o
build, verificar `web/out/licenses/fonts/` e preservar essa pasta na distribuição.

Para conferir ou atualizar, use o caminho da tabela e uma revisão completa:

```text
https://raw.githubusercontent.com/google/fonts/<commit>/<caminho-na-origem>
```

Ao atualizar, revisar os avisos de licença, verificar os hashes e os caracteres
utilizados pela interface e executar o build. Não substituir estes arquivos por
fontes simuladas nem desabilitar verificações de rede para concluir o build.
