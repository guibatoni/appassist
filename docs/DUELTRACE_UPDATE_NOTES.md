# DUELTRACE v0.15.0 — Preview

## Novidades
- **Análise automática dos tipos por ISO:** a importação e a opção Atualizar dados auditam os códigos de tipo realmente lidos nos registros do executável PS1 do mod ativo.
- **Identificação de tipos personalizados:** códigos fora do padrão 0–23, suspeitas de remapeamento e cartas isoladas incompatíveis com as regras originais ficam identificados como **Tipo #N (a verificar)**.
- **Relatório local por mod:** o arquivo `tipos_iso.json` registra códigos encontrados, quantidades e evidências, vinculado ao SHA-256 da ISO, sem modificar a imagem original.

## Melhorias
- **Cartas mais fiéis aos mods:** Biblioteca, Fusões, Drops e Mão priorizam o tipo detectado para cada ISO, em vez de aplicar indiscriminadamente a tabela fixa do jogo original.
- **ATK e DEF preservados:** cartas com evidências estruturais de monstro continuam exibindo as estatísticas realmente extraídas, sem inventar nomes de classes.
- **Cache atualizado automaticamente:** a revisão do scanner força nova análise após atualização de dados, e o render HD é regenerado quando a classificação muda.

## Correções
- **Sem herança entre mods:** uma interpretação de tipo de outra ISO não é reutilizada; o relatório exige SHA-256 correspondente.
- **Molduras seguras:** tipos desconhecidos ou suspeitos não recebem arbitrariamente a moldura de magia, ritual ou armadilha do jogo original.
- **Confiança explícita:** códigos compatíveis não comprovam semântica idêntica ao original. Quando a ISO não fornece uma tabela confiável de nomes de tipos, a classificação exata permanece pendente de validação, inclusive em duelo.
