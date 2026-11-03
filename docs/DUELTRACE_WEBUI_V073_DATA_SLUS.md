# DUELTRACE WebUI 0.7.3 — varredura WA_MRG + SLUS por ISO

## Princípio
Extrair dados observáveis do BIN/ISO **local**, associar cada item ao SHA-256 da imagem e manter seu endereço original. Nenhuma ROM, asset protegido ou efeito da ISO é enviado a serviços externos; não adicionar ROMs ao GitHub.

## Fontes e dados

| Arquivo | Recursos | Extração | Limites |
|---|---|---|---|
| SLUS_014.11 | 722 IDs, nomes, ATK/DEF, tipo | Parser já existente com validação estrutural | Outros layouts podem divergir |
| SLUS_014.11 | 722 descrições impressas | Tabela de ponteiros em `0x1B0A00`, base `0x1B0800`, fonte em `0x1C9800`; rejeita banco se menos de 600 descrições plausíveis | Texto impresso **não confirma** efeito de jogo |
| WA_MRG.MRG | 722 artes 102×96 | Sete setores por carta a partir do setor 722; PNG e índice por ID (scanner existente) | A arte só é ativada após extração local com estrutura reconhecida |
| WA_MRG.MRG | molduras coloridas por categoria | Paletas das linhas 248–253 do pacote de campo Normal, tabelas BGR555, offsets preservados | A CLUT dá cores, **não a geometria completa da moldura original** |
| WA_MRG.MRG | fusões e drops | Investigadores estruturais existentes, sem herdar entre mods | Marcados por procedência e revisões |

## Comportamento em cada mod
- O scanner lê tanto o arquivo SLUS como o prefixo WA que contém os recursos em todas as reanálises.
- As descrições recebem `description_source` e `description_offset`, enquanto o campo `effect_text` permanece reservado a manifestos estruturados com origem rastreável.
- Perfis antigos sem `disc_metadata_revision=1` são recalculados na próxima ativação/consulta de reanálise; a revisão do parser de arte foi incrementada.
- O botão **Reanalisar arte, descrições e molduras** no cartão de cada mod executa uma nova leitura real da ISO local, verifica que o SHA continua o mesmo e não modifica o arquivo.
- A Biblioteca mostra descrição separada do efeito e usa cores reais das paletas WA disponíveis. Nome, ID, ATK e DEF continuam visíveis.
- Os efeitos de cartas especiais podem depender de rotinas do executável, e não necessariamente de um texto de descrição. Não marcar como comprovado sem extrair e validar a tabela/rotina correspondente.

## Regras de segurança
- Rejeitar texto/ponteiro sem terminação ou que saia do banco; não buscar strings aleatórias e atribuí-las a cartas.
- Não reutilizar dados de outra ISO por nome; perfil e artes ficam vinculados ao SHA-256 da própria imagem.
- Não usar rede para análise; somente ISO/BIN selecionado pelo usuário.
- Separar o esquema do texto extraído, o efeito declarado e o efeito observado no duelo.
- Não sobrescrever evidências manuais previamente confirmadas na importação.
- Não embutir artes, ROMs ou molduras comerciais no aplicativo distribuído; os PNGs só são gerados localmente quando o usuário disponibiliza a sua própria ISO.

## O que ainda depende de teste real
- Verificar taxa de descrições válidas e codificação por glifos com cada variante de mod (incluindo 13 Drop x15, Original x15 e Remaster). O teste sintético não é prova para nenhum deles.
- Descobrir/cortar a geometria exata das molduras a partir dos pacotes gráficos da WA: esta entrega usa as CLUTs reais, não uma cópia do frame bitmap.
- Mapear as tabelas e rotinas de efeitos e verificar modificações de cada mod; descrever não basta.
- Conferir a interface WebView2, a posição das molduras e a leitura de ATK/DEF com o ePSXe real.

## Fontes técnicas consultadas
- `Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled`, `notes/mrg-files.md`, `notes/modding-tutorial-evidence.md` e `tools/pc/extract_images.py` (modelo de arquivo MRG, CLUTs e imagens).
- `forbidden-memories-coding/fmscrambler`, `FMLib/Randomizer/DataScrambler.cs` (tabela de ponteiros de descrição no SLUS).
- A referência técnica não autoriza reproduzir nem distribuir ROMs/arte de terceiros no app comercial.
