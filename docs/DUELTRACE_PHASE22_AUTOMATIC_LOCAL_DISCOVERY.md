# DUELTRACE - Etapa 22: descoberta automática local

Estado: Preview experimental, sem merge na main. Não modifica ISO, save, Memory Card, RAM, catálogo ou artes.

## Entregas
- Biblioteca exibe automaticamente matrizes estruturais diretamente da ISO selecionada, sem pedir duelos manuais.
- Para o GOG MOD 2.2, mostra os 40 blocos físicos e quatro matrizes de cada bloco: 0 deck candidato, 1 a 3 distribuições de recompensa candidatas.
- Usa o catálogo de 722 cartas do próprio mod para nomes, ATK e DEF e calcula a fração peso/2048, sem assumir rótulos de RANK.
- Quando há só um bloco candidato nas evidências locais, sugere-o automaticamente, ainda sem promoção.
- Ficha ativa consulta automaticamente o ID de adversário candidato no ePSXe por RAM PS1, exigindo LP, mão e histórico de compras coerentes.
- Se o ePSXe foi iniciado pelo próprio DUELTRACE para a ISO atualmente selecionada, mudanças do ID de RAM candidato são registradas automaticamente em arquivo local separado por SHA da ISO. O log é provisório e nunca desbloqueia drops nem prova a ISO em execução.
- APIs com token de sessão; leitura de processo somente com privilégios QUERY e VM_READ.

## Documentação de formato PS1 original
- Byte de ID do adversário no NTSC-U: PS1 0x8009B361.
- LP: PS1 0x800EA004 e 0x800EA024.
- Histórico de compras: offset PS1 0x1A7E20.
- Referências: https://datacrystal.tcrf.net/wiki/Yu-Gi-Oh%21_Forbidden_Memories/RAM_map
- Referência: https://github.com/Robertdark/FMHelper/blob/main/MEMORY_MAP.md
- Referência: https://github.com/Unchiga/Yu-Gi-Oh-Forbidden-Memories-Recompiled/blob/master/notes/rng.md

**Cuidado:** estes endereços são conhecidos para a família original. Ainda não foram validados em execução no GOG 2.2. O endereço host do ePSXe é encontrado e conferido, não presumido.

## Segurança e honestidade dos resultados
- O explorador exige família estrutural única, verifica 39 blocos completos, compara SHA da ISO e hash do recurso quando disponível.
- Pesos e porcentagens são condicionais ao grupo ainda sem rótulo e não constituem taxa oficial de drop.
- O monitor de RAM usa somente ePSXe.exe, duas amostras estáveis e verificações independentes. Se houver mapeamento ambíguo não devolve ID.
- Nenhuma estrutura do catálogo oficial de drops, fusões ou RANK é ativada por hipótese. Nenhum dado da ROM é enviado à nuvem.

## Pendências para compatibilidade completa
1. Confirmar em execução real os offsets PS1 para o GOG e seus formatos.
2. Relacionar o ID observado em RAM ao bloco de decks e recompensas por referência de código MIPS.
3. Descobrir a classificação correta de cada grupo de RANK e preservar os dados da Biblioteca já validados.
4. Adaptar a outros emuladores/mods quando mudarem os offsets e codecs.

Objetivo desta etapa: dados locais consultáveis automaticamente e ID de adversário observável, não exigir mais registro manual apenas para visualizar matrizes.