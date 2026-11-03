# DUELTRACE WebUI 0.7.3 — Leitura aprofundada de WA_MRG.MRG e SLUS_014.11

## Objetivo
Extrair dados e recursos presentes na própria ISO/BIN local selecionada, vinculados ao SHA-256 da imagem. Não distribuir ROMs, arquivos do jogo, texturas ou efeitos protegidos por direitos autorais no GitHub, Vercel ou instalador.

## Arquivos procurados automaticamente
- `DATA/WA_MRG.MRG` (qualquer pasta com o nome-base `WA_MRG.MRG`). É um arquivo binário de recursos, **não** `WA_WRG.MRG` (troca provável de letras).
- `SLUS_014.11` na raiz ou em `DATA/`, e variantes SLUS/SLPS quando o ISO9660 as apresentar. O scanner valida se os ponteiros e tabelas são plausíveis antes de atribuir a um ID.
- O scanner lê o índice ISO9660, não busca bytes arbitrários fora dos arquivos. Para ler todas as imagens e os quadros originais, a opção de artes deve estar ativa; importar via WebUI ou clicar `Ler WA_MRG + SLUS novamente` executa essa leitura.

## Estruturas identificadas
| Informação | Arquivo | Endereço relativo | Resultado |
|---|---|---|---|
| Nome das 722 cartas | SLUS | tabela `0x1C6000`, banco `0x1C0800` | Nome com ID vinculado |
| ATK/DEF/tipo/duas estrelas | SLUS | tabela `0x1C4A44`, 4 B por carta | Valores numéricos verificáveis |
| Nível e atributo | SLUS | tabela `0x1C5B33`, 1 B por carta | Código numérico sem inferência |
| Descrição | SLUS | ponteiros u16 `0x1B0A02 + 2*(id-1)` → texto `0x1B0800+ponteiro` | Texto e offset da origem se ≥500/722 válidos |
| Imagem 102×96, 256 cores | WA_MRG | setor `722+7*(id-1)`, paleta `+0x2640` | PNG grande local por ID |
| Miniatura 40×32, 64 cores | WA_MRG | setor `id-1` e cópia no registro `+0x2AE0` | PNG local por ID com comparação das duas cópias |
| Moldura original do duelo | WA_MRG | pacote `0xB63000`, textura fase0/CLUT fase1 | Seis molduras 52×60 com paletas originais |
| Composição moldura + miniatura | WA_MRG | UV da mão do jogo, imagem x+6/y+6 | PNG local `cartas_com_moldura/###.png` |

Os offsets seguem o formato clássico Forbidden Memories e engenharia reversa pública, **não são garantidos para todo mod**. O scanner não inventa descrições, efeitos, arquivos ou artes quando a estrutura diverge.

## Estrutura de saída local
- `analises/<mod_sha>/artes_722/001.png`: arte grande
- `analises/<mod_sha>/miniaturas_722/001.png`: miniatura do jogo
- `analises/<mod_sha>/molduras_wa/0-monstro.png` até `5-laranja.png`: quadros com cores originais
- `analises/<mod_sha>/cartas_com_moldura/001.png`: prévia composta por ID/tipo
- `analises/<mod_sha>/recursos_wa.json`: offsets, SHA do WA integral, validação de miniaturas, contagem de artes e erros
- `analises/<mod_sha>/cartas.csv`: 722 linhas com nome, ATK, DEF, tipo, nível, atributo, estrelas, descrição e fonte/offset quando extraídos
- `profiles/<sha>/profile.json`: catálogo local que a interface usa; números não confirmados ficam vazios.

## Efeitos e descrições: não confundir conceitos
- **Descrição:** texto da tabela SLUS, associada por ponteiro e ID (não é, sozinha, prova de mecânica).
- **Texto indicativo de efeito:** descrição de Mágica/Armadilha/Ritual/Equipamento ou descrição de monstro com marcador `<Effect>`/`<Efeito>`. Fonte SLUS preservada e status `texto_do_jogo_sem_confirmacao_de_mecanica`.
- **Efeito executado:** exige disassembly da rotina usada pelo mod e validação no duelo; nenhuma descrição textual será apresentada como comprovação dessa mecânica.
- Mods com manifesto `DTEFFECT.JSON` ou manifesto local de efeito vinculado ao SHA ainda são suportados, com procedência explícita.

## Interface
- Biblioteca de Cartas e Biblioteca de Fusões exibem a miniatura com **moldura do próprio WA_MRG** se disponível; se não houver moldura, usam a arte grande; caso contrário, mostram placeholder.
- Nome/ID são sempre separados e legíveis; monstros apresentam **ATK e DEF** na biblioteca, no detalhe, nas fusões e na mão.
- Ao selecionar carta, veja a descrição automática e a fonte, além de texto de efeito quando identificado.
- Biblioteca de Mods tem botão `Ler WA_MRG + SLUS novamente`: reanalisa o arquivo original presente no PC e exibe totais reais de artes, molduras, descrições e textos indicativos.

## Segurança, limites e próximos testes
- Scanner lê ISO local em modo somente leitura, nunca grava na ROM, RAM ou Memory Card.
- WA tem limite de 96 MiB para evitar leitura arbitrariamente grande em memória; contagens parciais não se tornam flags de sucesso.
- Cada PNG servido pela WebUI é restringido ao SHA do mod **ativo**, à pasta `analises`, com rotas sem listagem de diretório e token nativo.
- Fotos, ISOs e dados pessoais não são enviados ao Vercel ou GitHub pelos métodos novos.
- O pipeline Windows contém testes sintéticos de offsets, paletas, textos, token de acesso e backup de fusões já verificadas.
- **Falta validar com os arquivos reais do usuário no Windows**, inclusive posição/cores das molduras e conteúdo do SLUS modificado. Nenhuma promessa de extração perfeita para todas as versões.
- A versão v0.7.3 continua **Preview não assinada**; não lançar comercialmente antes da revisão e assinatura digital.

## Referências públicas usadas na investigação
- `https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/tools/pc/extract_images.py`
- `https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/src/game/duel_card_frame_draw.c`
- `https://github.com/vishtheshnu/forbidden-memories-fusion-finder/blob/master/filereader.py`
